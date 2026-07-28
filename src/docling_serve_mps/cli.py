"""Minimal background lifecycle for the Docling Serve MPS sidecar."""

from __future__ import annotations

import argparse
import fcntl
import importlib
import json
import os
import platform
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterator, Mapping, Sequence

COMMAND_MARKER = "-m docling_serve run"
OCR_PRESET = (
    '{"auto":{"kind":"ocrmac","framework":"vision",'
    '"recognition":"accurate","lang":["zh-Hans","en-US"]}}'
)

DEFAULT_ENVIRONMENT = {
    "DOCLING_DEVICE": "mps",
    "PYTORCH_ENABLE_MPS_FALLBACK": "1",
    "DOCLING_NUM_THREADS": "8",
    "OMP_NUM_THREADS": "8",
    "VECLIB_MAXIMUM_THREADS": "8",
    "DOCLING_SERVE_ENG_LOC_NUM_WORKERS": "1",
    "DOCLING_SERVE_LOAD_MODELS_AT_BOOT": "true",
    "DOCLING_SERVE_OPTIONS_CACHE_SIZE": "2",
    "DOCLING_HOST": "127.0.0.1",
    "DOCLING_PORT": "5001",
    "UVICORN_WORKERS": "1",
    "DOCLING_SERVE_ENABLE_UI": "true",
    "DOCLING_SERVE_ENABLE_REMOTE_SERVICES": "false",
    "DOCLING_SERVE_ALLOW_EXTERNAL_PLUGINS": "false",
    "DOCLING_SERVE_SINGLE_USE_RESULTS": "true",
    "DOCLING_SERVE_LOG_LEVEL": "INFO",
    "DOCLING_SERVE_LOG_FORMAT": "text",
    "DOCLING_SERVE_CUSTOM_OCR_PRESETS": OCR_PRESET,
}


class ServiceError(RuntimeError):
    """A user-actionable lifecycle failure."""


@dataclass(frozen=True)
class ServicePaths:
    """Persistent files owned by one user-level service instance."""

    root: Path

    @classmethod
    def from_environment(cls) -> ServicePaths:
        configured = os.environ.get("DOCLING_SERVE_MPS_STATE_DIR")
        if configured:
            return cls(Path(configured).expanduser())
        return cls(
            Path.home()
            / "Library"
            / "Application Support"
            / "docling-serve-mps"
        )

    @property
    def pid(self) -> Path:
        return self.root / "docling-serve.pid"

    @property
    def log(self) -> Path:
        return self.root / "docling-serve.log"

    @property
    def scratch(self) -> Path:
        return self.root / "scratch"

    @property
    def lock(self) -> Path:
        return self.root / "lifecycle.lock"


def build_child_environment(
    paths: ServicePaths,
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Apply secure package defaults without overriding explicit values."""

    environment = dict(os.environ if source is None else source)
    for name, value in DEFAULT_ENVIRONMENT.items():
        environment.setdefault(name, value)
    environment.setdefault("DOCLING_SERVE_SCRATCH_PATH", str(paths.scratch))
    return environment


def validate_platform() -> None:
    if sys.platform != "darwin" or platform.machine().lower() != "arm64":
        raise ServiceError("docling-serve-mps requires macOS on Apple Silicon.")


def validate_runtime() -> None:
    """Fail before daemonizing when the installed tool environment is invalid."""

    validate_platform()
    for module_name in ("docling_serve", "ocrmac"):
        try:
            importlib.import_module(module_name)
        except ImportError as exc:
            raise ServiceError(
                f"The installed environment is missing {module_name}. Reinstall "
                "docling-serve-mps with uv tool install --force."
            ) from exc

    torch = importlib.import_module("torch")
    if not torch.backends.mps.is_available():
        raise ServiceError("PyTorch MPS is not available on this Mac.")


def process_command(pid: int) -> str | None:
    """Return the full command for a live process, or None when it is gone."""

    result = subprocess.run(
        ["ps", "-ww", "-p", str(pid), "-o", "stat=", "-o", "command="],
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    if result.returncode != 0 or not output:
        return None
    state, separator, command = output.partition(" ")
    if state.startswith("Z") or not separator or not command.strip():
        return None
    return command.strip()


def _load_pid_record(paths: ServicePaths) -> dict[str, object] | None:
    try:
        payload = json.loads(paths.pid.read_text(encoding="utf-8"))
        pid = int(payload["pid"])
        marker = str(payload["command_marker"])
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        paths.pid.unlink(missing_ok=True)
        return None
    return {"pid": pid, "command_marker": marker}


def _write_pid_record(paths: ServicePaths, pid: int) -> None:
    temporary = paths.pid.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"pid": pid, "command_marker": COMMAND_MARKER}),
        encoding="utf-8",
    )
    temporary.replace(paths.pid)


@contextmanager
def _lifecycle_lock(paths: ServicePaths) -> Iterator[None]:
    paths.root.mkdir(parents=True, exist_ok=True)
    with paths.lock.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        yield


def _service_url(environment: Mapping[str, str], path: str = "") -> str:
    host = environment["DOCLING_HOST"]
    port = environment["DOCLING_PORT"]
    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{display_host}:{port}{path}"


def health_ready(environment: Mapping[str, str]) -> bool:
    try:
        with urllib.request.urlopen(
            _service_url(environment, "/health"), timeout=2.0
        ) as response:
            return response.status == 200
    except (OSError, TimeoutError, urllib.error.URLError):
        return False


def wait_for_health(
    environment: Mapping[str, str],
    pid: int,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if health_ready(environment):
            return
        if process_command(pid) is None:
            raise ServiceError("Docling Serve exited before becoming healthy.")
        time.sleep(0.5)
    raise ServiceError(
        "Docling Serve is still starting. Run start again to continue the health check."
    )


def _child_command(environment: Mapping[str, str]) -> list[str]:
    return [
        sys.executable,
        "-m",
        "docling_serve",
        "run",
        "--host",
        environment["DOCLING_HOST"],
        "--port",
        environment["DOCLING_PORT"],
        "--workers",
        environment["UVICORN_WORKERS"],
    ]


def _spawn_service(
    paths: ServicePaths,
    environment: Mapping[str, str],
) -> subprocess.Popen[bytes]:
    paths.scratch.mkdir(parents=True, exist_ok=True)
    log_file: IO[bytes]
    with paths.log.open("ab", buffering=0) as log_file:
        return subprocess.Popen(
            _child_command(environment),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=paths.root,
            env=dict(environment),
            start_new_session=True,
            close_fds=True,
        )


def start_service(
    *,
    paths: ServicePaths | None = None,
    timeout: float | None = None,
) -> str:
    validate_runtime()
    resolved_paths = paths or ServicePaths.from_environment()
    environment = build_child_environment(resolved_paths)
    start_timeout = timeout or float(
        os.environ.get("DOCLING_SERVE_MPS_START_TIMEOUT", "300")
    )

    with _lifecycle_lock(resolved_paths):
        record = _load_pid_record(resolved_paths)
        if record is not None:
            pid = int(record["pid"])
            marker = str(record["command_marker"])
            if marker != COMMAND_MARKER:
                resolved_paths.pid.unlink(missing_ok=True)
                record = None
            else:
                command = process_command(pid)
                if command and marker in command:
                    if not health_ready(environment):
                        wait_for_health(environment, pid, start_timeout)
                    return _started_message(
                        resolved_paths, environment, pid, already_running=True
                    )
                resolved_paths.pid.unlink(missing_ok=True)

        child = _spawn_service(resolved_paths, environment)
        _write_pid_record(resolved_paths, child.pid)
        try:
            wait_for_health(environment, child.pid, start_timeout)
        except ServiceError:
            if child.poll() is not None:
                resolved_paths.pid.unlink(missing_ok=True)
            raise
        return _started_message(resolved_paths, environment, child.pid)


def _started_message(
    paths: ServicePaths,
    environment: Mapping[str, str],
    pid: int,
    *,
    already_running: bool = False,
) -> str:
    state = "Docling Serve is already running" if already_running else "Started Docling Serve"
    return "\n".join(
        (
            f"{state} (PID {pid}).",
            f"API: {_service_url(environment)}",
            f"UI: {_service_url(environment, '/ui/')}",
            f"Log: {paths.log}",
        )
    )


def stop_service(
    *,
    paths: ServicePaths | None = None,
    timeout: float = 15.0,
) -> str:
    resolved_paths = paths or ServicePaths.from_environment()
    with _lifecycle_lock(resolved_paths):
        record = _load_pid_record(resolved_paths)
        if record is None:
            return "Docling Serve is not running."

        pid = int(record["pid"])
        marker = str(record["command_marker"])
        if marker != COMMAND_MARKER:
            resolved_paths.pid.unlink(missing_ok=True)
            raise ServiceError(
                f"Refusing to stop unrelated process {pid}; removed stale state."
            )
        command = process_command(pid)
        if command is None:
            resolved_paths.pid.unlink(missing_ok=True)
            return "Removed stale Docling Serve state."
        if marker not in command:
            resolved_paths.pid.unlink(missing_ok=True)
            raise ServiceError(
                f"Refusing to stop unrelated process {pid}; removed stale state."
            )

        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process_command(pid) is None:
                resolved_paths.pid.unlink(missing_ok=True)
                return f"Stopped Docling Serve (PID {pid})."
            time.sleep(0.1)
        raise ServiceError(f"Docling Serve PID {pid} did not stop after SIGTERM.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docling-serve-mps",
        description="Manage native Docling Serve on Apple Silicon.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("start", help="Start the background service.")
    commands.add_parser("stop", help="Stop the background service.")
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        message = start_service() if arguments.command == "start" else stop_service()
    except ServiceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(message)
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
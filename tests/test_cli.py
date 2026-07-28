import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from docling_serve_mps import cli


class CliContractTest(unittest.TestCase):
    def test_parser_exposes_only_start_and_stop(self) -> None:
        parser = cli.build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if action.__class__.__name__ == "_SubParsersAction"
        )

        self.assertEqual(set(subparsers.choices), {"start", "stop"})

    def test_child_environment_has_secure_mps_ocr_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            paths = cli.ServicePaths(Path("/tmp/docling-serve-mps-test"))
            environment = cli.build_child_environment(paths)

        self.assertEqual(environment["DOCLING_DEVICE"], "mps")
        self.assertEqual(environment["DOCLING_HOST"], "127.0.0.1")
        self.assertEqual(environment["DOCLING_SERVE_ENABLE_REMOTE_SERVICES"], "false")
        self.assertEqual(environment["DOCLING_SERVE_ALLOW_EXTERNAL_PLUGINS"], "false")
        self.assertIn('"kind":"ocrmac"', environment["DOCLING_SERVE_CUSTOM_OCR_PRESETS"])
        self.assertIn('"lang":["zh-Hans","en-US"]', environment["DOCLING_SERVE_CUSTOM_OCR_PRESETS"])

    def test_explicit_environment_overrides_defaults(self) -> None:
        with patch.dict(os.environ, {"DOCLING_PORT": "5101"}, clear=True):
            environment = cli.build_child_environment(
                cli.ServicePaths(Path("/tmp/docling-serve-mps-test"))
            )

        self.assertEqual(environment["DOCLING_PORT"], "5101")

    def test_platform_validation_rejects_non_apple_silicon(self) -> None:
        with (
            patch.object(cli.sys, "platform", "linux"),
            self.assertRaisesRegex(cli.ServiceError, "macOS on Apple Silicon"),
        ):
            cli.validate_platform()

    def test_start_is_idempotent_for_healthy_managed_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = cli.ServicePaths(Path(temporary_directory))
            paths.root.mkdir(parents=True, exist_ok=True)
            paths.pid.write_text(
                json.dumps({"pid": 4321, "command_marker": cli.COMMAND_MARKER}),
                encoding="utf-8",
            )
            with (
                patch.object(cli, "validate_runtime"),
                patch.object(cli, "process_command", return_value=cli.COMMAND_MARKER),
                patch.object(cli, "health_ready", return_value=True),
                patch.object(cli.subprocess, "Popen") as popen,
            ):
                result = cli.start_service(paths=paths)

        self.assertIn("already running", result)
        popen.assert_not_called()

    def test_start_replaces_dead_pid_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = cli.ServicePaths(Path(temporary_directory))
            paths.root.mkdir(parents=True, exist_ok=True)
            paths.pid.write_text(
                json.dumps({"pid": 999999, "command_marker": cli.COMMAND_MARKER}),
                encoding="utf-8",
            )
            child = Mock(pid=5432)
            child.poll.return_value = None
            with (
                patch.object(cli, "validate_runtime"),
                patch.object(cli, "process_command", return_value=None),
                patch.object(cli, "wait_for_health"),
                patch.object(cli.subprocess, "Popen", return_value=child),
            ):
                result = cli.start_service(paths=paths)

            record = json.loads(paths.pid.read_text(encoding="utf-8"))

        self.assertEqual(record["pid"], 5432)
        self.assertIn("Started", result)

    def test_stop_refuses_to_signal_unrelated_reused_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = cli.ServicePaths(Path(temporary_directory))
            paths.root.mkdir(parents=True, exist_ok=True)
            paths.pid.write_text(
                json.dumps({"pid": 4321, "command_marker": cli.COMMAND_MARKER}),
                encoding="utf-8",
            )
            with (
                patch.object(cli, "process_command", return_value="/usr/bin/unrelated"),
                patch.object(cli.os, "kill") as kill,
                self.assertRaisesRegex(cli.ServiceError, "unrelated process"),
            ):
                cli.stop_service(paths=paths)

            kill.assert_not_called()
            self.assertFalse(paths.pid.exists())

    def test_stop_terminates_managed_process(self) -> None:
        marker = "docling-serve-mps-test-process"
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)", marker]
        )
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                paths = cli.ServicePaths(Path(temporary_directory))
                paths.root.mkdir(parents=True, exist_ok=True)
                paths.pid.write_text(
                    json.dumps({"pid": process.pid, "command_marker": marker}),
                    encoding="utf-8",
                )

                result = cli.stop_service(paths=paths, timeout=5.0)

                self.assertIn("Stopped", result)
                self.assertFalse(paths.pid.exists())
                self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
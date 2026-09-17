"""Foreground entry point: install the packaged defaults, then serve.

``python -m docling_serve_mps.launcher run --host H --port P --workers N`` takes
the same arguments as ``docling-serve run``. Both the daemonizing ``start`` mode
and the foreground ``run`` mode exec this module, because one packaged default
cannot be expressed as an environment variable: docling freezes its implicit
code/formula stage spec at import time, so it has to be replaced before
docling's pipeline options are imported (see
:mod:`docling_serve_mps.defaults`).

Docling Serve itself is imported only after that substitution, and the running
server is the one the CLI would have started -- this module adds a default and
nothing else.
"""

from __future__ import annotations

import sys
from typing import Sequence

from docling_serve_mps import defaults
from docling_serve_mps.cli import ServiceError


def _declared_workers(arguments: Sequence[str]) -> int | None:
    for position, argument in enumerate(arguments):
        if argument == "--workers" and position + 1 < len(arguments):
            value = arguments[position + 1]
        elif argument.startswith("--workers="):
            value = argument.split("=", 1)[1]
        else:
            continue
        try:
            return int(value)
        except ValueError:
            return None
    return None


def main() -> None:
    try:
        repository = defaults.apply_implicit_code_formula_default()
        repository = defaults.verify_implicit_code_formula_default()
    except ServiceError as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc

    print(
        f"[docling-serve-mps] implicit code/formula default: {repository} (MLX)",
        flush=True,
    )

    workers = _declared_workers(sys.argv)
    if workers is not None and workers > 1:
        # Uvicorn's worker processes re-import the app through its import string,
        # so an in-process substitution made here does not reach them.
        print(
            f"[docling-serve-mps] warning: --workers {workers} serves from "
            "uvicorn worker processes that import docling on their own, so the "
            "packaged code/formula default only applies to a single worker",
            file=sys.stderr,
            flush=True,
        )

    from docling_serve.__main__ import main as serve

    serve()


if __name__ == "__main__":
    main()

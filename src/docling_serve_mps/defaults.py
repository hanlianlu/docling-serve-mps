"""Packaged Docling defaults that no environment variable can express.

Docling Serve resolves a stage preset only when the request names one:
docling-jobkit's converter manager guards every lookup with
``if request.code_formula_preset:``. A request that enables code or formula
enrichment without naming a preset therefore never reaches the preset registry
and lands on docling's own module-level default instead -- the ``codeformulav2``
stage spec, whose only engine is Transformers, which refuses MPS outright
(``MPS is not supported by this model``). Docling Serve's own UI sends exactly
that request: its enrichment checkboxes carry no preset.

Configuration cannot reach that path. ``DOCLING_SERVE_DEFAULT_CODE_FORMULA_
PRESET`` only fills the registry entry that a client selects by *sending*
``default``, and the request model's ``code_formula_preset`` defaults to
``None``, so "absent" never consults the registry at all.

What is left is the one substitution this module performs: docling builds that
implicit default from ``stage_model_specs.CODE_FORMULA_CODEFORMULAV2`` at import
time, so replacing that spec before ``docling.datamodel.pipeline_options`` is
imported makes the implicit path resolve to the granite-docling spec docling
already ships for Apple Silicon. Preset *lookups* stay untouched, so a client
that names ``default`` or ``granite_docling`` still goes through the registry --
to the same model -- and a client that names ``codeformulav2`` is still refused
by the allow-list in :mod:`docling_serve_mps.cli`.

Both halves are checked at startup rather than trusted: a docling release that
renames either stage spec or drops the MLX engine makes the service refuse to
start with a stated reason, instead of failing one conversion at a time.
"""

from __future__ import annotations

import sys
from typing import Any

from docling_serve_mps.cli import ServiceError

IMPLICIT_PRESET_ID = "codeformulav2"
"""Preset docling hardcodes as its implicit code/formula default."""

MPS_PRESET_ID = "granite_docling"
"""Preset that serves the same stage with an MLX engine on Apple Silicon."""

_PIPELINE_OPTIONS_MODULE = "docling.datamodel.pipeline_options"
_APPLIED_REPO: str | None = None


def apply_implicit_code_formula_default() -> str:
    """Make docling's implicit code/formula default the MPS-capable spec.

    Returns the model repository that default now resolves to. Raises
    :class:`ServiceError` when docling's stage specs no longer have the shape
    this substitution depends on, or when it is called after docling's pipeline
    options have already been imported -- the point where the substitution would
    silently stop having any effect.
    """

    global _APPLIED_REPO
    if _APPLIED_REPO is not None:
        return _APPLIED_REPO

    if _PIPELINE_OPTIONS_MODULE in sys.modules:
        raise ServiceError(
            "docling's pipeline options were imported before the packaged "
            "code/formula default could be installed, so the implicit default "
            "would still be the Transformers-only CodeFormulaV2 preset. Import "
            "docling_serve_mps.defaults before anything that loads docling."
        )

    # Importing the stage specs is free of that constraint; the pipeline options
    # module is the one that freezes its defaults out of them.
    from docling.datamodel import stage_model_specs

    implicit = getattr(stage_model_specs, "CODE_FORMULA_CODEFORMULAV2", None)
    mps = getattr(stage_model_specs, "CODE_FORMULA_GRANITE_DOCLING", None)
    if implicit is None or mps is None:
        raise ServiceError(
            "docling no longer exposes CODE_FORMULA_CODEFORMULAV2 and "
            "CODE_FORMULA_GRANITE_DOCLING, so the packaged code/formula default "
            "cannot be installed. Re-check docling's stage model specs."
        )
    if implicit.preset_id != IMPLICIT_PRESET_ID:
        raise ServiceError(
            f"docling's implicit code/formula stage spec is now "
            f"{implicit.preset_id!r}, not {IMPLICIT_PRESET_ID!r}; the packaged "
            "default would not be the one docling builds its pipeline from."
        )

    substitute = mps.model_copy(
        update={
            "preset_id": implicit.preset_id,
            "name": f"{mps.name} (MPS substitute for {IMPLICIT_PRESET_ID})",
            "description": (
                f"Same stage as the {MPS_PRESET_ID} preset, served by MLX: "
                f"docling's implicit {IMPLICIT_PRESET_ID} default has no engine "
                "that can run on Apple Silicon."
            ),
        }
    )
    stage_model_specs.CODE_FORMULA_CODEFORMULAV2 = substitute
    _APPLIED_REPO = substitute.model_spec.default_repo_id
    return _APPLIED_REPO


def implicit_code_formula_options() -> Any:
    """The options docling builds for a request that names no preset."""

    from docling.datamodel.pipeline_options import PdfPipelineOptions

    return PdfPipelineOptions().code_formula_options


def verify_implicit_code_formula_default() -> str:
    """Confirm the implicit default survived docling's import and runs on MPS."""

    from docling.datamodel.vlm_engine_options import VlmEngineType

    model_spec = implicit_code_formula_options().model_spec
    engines = model_spec.engine_overrides or {}
    if VlmEngineType.MLX not in engines:
        raise ServiceError(
            f"docling's implicit code/formula default is still "
            f"{model_spec.default_repo_id}, which ships no MLX engine, so a "
            "request that enables code or formula enrichment without naming a "
            "preset cannot run on MPS."
        )
    return model_spec.default_repo_id

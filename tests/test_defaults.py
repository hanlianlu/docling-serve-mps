import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from docling_serve_mps.cli import ServicePaths, build_child_environment

APPLY_SCRIPT = """
import json

from docling_serve_mps import defaults

repository = defaults.apply_implicit_code_formula_default()
verified = defaults.verify_implicit_code_formula_default()

import warnings

from docling.datamodel.service.options import ConvertDocumentsOptions
from docling_jobkit.convert.manager import DoclingConverterManager
from docling_serve.orchestrator_factory import _build_cm_config

manager = DoclingConverterManager(_build_cm_config())

# The implicit path (no preset in the request) is what the UI sends.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    implicit = manager._parse_code_formula_options(ConvertDocumentsOptions())
implicit_spec = defaults.implicit_code_formula_options().model_spec

# A client that names a preset still goes through the registry.
named = {}
for requested in ("default", "granite_docling"):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        request = ConvertDocumentsOptions(code_formula_preset=requested)
    spec = manager._parse_code_formula_options(request).model_spec
    named[requested] = {
        "repo_id": spec.default_repo_id,
        "engines": sorted(engine.value for engine in (spec.engine_overrides or {})),
    }

# The preset docling hardcodes is still refused by name.
try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        request = ConvertDocumentsOptions(code_formula_preset="codeformulav2")
    manager._parse_code_formula_options(request)
    refused = None
except Exception as exc:  # noqa: BLE001 - the rejection type is jobkit's business
    refused = str(exc)

print(json.dumps({
    "applied": repository,
    "verified": verified,
    "jobkit_implicit_is_none": implicit is None,
    "implicit": {
        "repo_id": implicit_spec.default_repo_id,
        "engines": sorted(engine.value for engine in (implicit_spec.engine_overrides or {})),
    },
    "named": named,
    "refused": refused,
}))
"""

GUARD_SCRIPT = """
import json

from docling.datamodel import stage_model_specs

from docling_serve_mps import defaults

stage_model_specs.CODE_FORMULA_GRANITE_DOCLING = None
try:
    defaults.apply_implicit_code_formula_default()
    outcome = "no error"
except defaults.ServiceError as exc:
    outcome = "raised: " + str(exc)
print(json.dumps({"outcome": outcome}))
"""

TOO_LATE_SCRIPT = """
import json

import docling.datamodel.pipeline_options  # noqa: F401 - imported first on purpose

from docling_serve_mps import defaults

try:
    defaults.apply_implicit_code_formula_default()
    outcome = "no error"
except defaults.ServiceError as exc:
    outcome = "raised: " + str(exc)
print(json.dumps({"outcome": outcome}))
"""


class ImplicitDefaultTest(unittest.TestCase):
    def run_script(self, script: str) -> dict[str, object]:
        environment = build_child_environment(
            ServicePaths(Path("/tmp/docling-serve-mps-test")), source=os.environ
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        return json.loads(result.stdout)

    def test_implicit_default_becomes_the_mlx_preset(self) -> None:
        outcome = self.run_script(APPLY_SCRIPT)

        self.assertEqual(outcome["applied"], "ibm-granite/granite-docling-258M")
        self.assertEqual(outcome["verified"], outcome["applied"])
        # jobkit leaves the options unset when no preset is named; docling's own
        # default is what a request without a preset actually runs.
        self.assertTrue(outcome["jobkit_implicit_is_none"])
        self.assertEqual(
            outcome["implicit"],
            {
                "repo_id": "ibm-granite/granite-docling-258M",
                "engines": ["mlx", "transformers"],
            },
        )

    def test_named_presets_still_resolve_through_the_registry(self) -> None:
        outcome = self.run_script(APPLY_SCRIPT)

        self.assertEqual(outcome["named"]["default"], outcome["named"]["granite_docling"])
        self.assertEqual(
            outcome["named"]["default"],
            {"repo_id": "ibm-granite/granite-docling-258M", "engines": ["mlx", "transformers"]},
        )
        self.assertEqual(outcome["named"]["default"], outcome["implicit"])

    def test_naming_the_implicit_preset_is_still_refused(self) -> None:
        outcome = self.run_script(APPLY_SCRIPT)

        self.assertIn("codeformulav2", str(outcome["refused"]))
        self.assertIn("not allowed", str(outcome["refused"]))

    def test_missing_docling_spec_fails_before_serving(self) -> None:
        outcome = self.run_script(GUARD_SCRIPT)

        self.assertIn("raised:", str(outcome["outcome"]))
        self.assertIn("CODE_FORMULA_GRANITE_DOCLING", str(outcome["outcome"]))

    def test_substitution_after_pipeline_import_is_reported(self) -> None:
        outcome = self.run_script(TOO_LATE_SCRIPT)

        self.assertIn("raised:", str(outcome["outcome"]))
        self.assertIn("imported before", str(outcome["outcome"]))


class LauncherTest(unittest.TestCase):
    def test_launcher_installs_the_default_then_hands_over_to_docling(self) -> None:
        # `-m` execution must reach main(): without a __main__ guard the module
        # imports, exits 0 and silently serves docling's own default.
        environment = build_child_environment(
            ServicePaths(Path("/tmp/docling-serve-mps-test")), source=os.environ
        )
        result = subprocess.run(
            [sys.executable, "-m", "docling_serve_mps.launcher", "--help"],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertIn("implicit code/formula default", result.stdout)
        self.assertIn("ibm-granite/granite-docling-258M", result.stdout)
        # Docling Serve's own CLI parsed the arguments and printed its usage.
        self.assertIn("Usage:", result.stdout)
        self.assertIn("Run a Docling Serve app in production mode", result.stdout)

    def test_declared_workers_is_read_from_the_passthrough_arguments(self) -> None:
        from docling_serve_mps.launcher import _declared_workers

        self.assertEqual(_declared_workers(["run", "--workers", "2"]), 2)
        self.assertEqual(_declared_workers(["run", "--workers=3"]), 3)
        self.assertEqual(_declared_workers(["run", "--workers", "1"]), 1)
        self.assertIsNone(_declared_workers(["run"]))
        self.assertIsNone(_declared_workers(["run", "--workers", "many"]))


if __name__ == "__main__":
    unittest.main()

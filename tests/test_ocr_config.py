import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from docling_serve_mps.cli import ServicePaths, build_child_environment


class OcrConfigTest(unittest.TestCase):
    def test_auto_preset_resolves_to_bilingual_vision_accurate(self) -> None:
        environment = build_child_environment(
            ServicePaths(Path("/tmp/docling-serve-mps-test")), source=os.environ
        )
        script = """
import json
import warnings
from docling.datamodel.service.options import ConvertDocumentsOptions
from docling_jobkit.convert.manager import DoclingConverterManager
from docling_serve.orchestrator_factory import _build_cm_config

manager = DoclingConverterManager(_build_cm_config())
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    request = ConvertDocumentsOptions(ocr_preset="auto", force_ocr=True)
options = manager._parse_ocr_options(request)
print(json.dumps({
    "source": manager.ocr_preset_registry["auto"]["source"],
    "class": type(options).__name__,
    "framework": options.framework,
    "recognition": options.recognition,
    "lang": options.lang,
    "force_full_page_ocr": options.force_full_page_ocr,
}))
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        configuration = json.loads(result.stdout)

        self.assertEqual(
            configuration,
            {
                "source": "custom",
                "class": "OcrMacOptions",
                "framework": "vision",
                "recognition": "accurate",
                "lang": ["zh-Hans", "en-US"],
                "force_full_page_ocr": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
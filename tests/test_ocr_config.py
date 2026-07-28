import unittest
import warnings

from docling.datamodel.pipeline_options import OcrMacOptions
from docling.datamodel.service.options import ConvertDocumentsOptions
from docling_jobkit.convert.manager import DoclingConverterManager
from docling_serve.orchestrator_factory import _build_cm_config


class OcrConfigTest(unittest.TestCase):
    def test_auto_preset_resolves_to_bilingual_vision_accurate(self) -> None:
        manager = DoclingConverterManager(_build_cm_config())

        self.assertEqual(manager.ocr_preset_registry["auto"]["source"], "custom")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            request = ConvertDocumentsOptions(ocr_preset="auto", force_ocr=True)
        options = manager._parse_ocr_options(request)

        self.assertIsInstance(options, OcrMacOptions)
        self.assertEqual(options.framework, "vision")
        self.assertEqual(options.recognition, "accurate")
        self.assertEqual(options.lang, ["zh-Hans", "en-US"])
        self.assertTrue(options.force_full_page_ocr)


if __name__ == "__main__":
    unittest.main()
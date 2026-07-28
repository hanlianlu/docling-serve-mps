import os
import tarfile
import unittest
import zipfile
from pathlib import Path


class DistributionContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        distribution_directory = Path(
            os.environ.get("DOCLING_SERVE_MPS_DIST_DIR", "dist")
        )
        wheels = sorted(distribution_directory.glob("*.whl"))
        source_distributions = sorted(distribution_directory.glob("*.tar.gz"))
        if len(wheels) != 1 or len(source_distributions) != 1:
            raise AssertionError(
                "expected exactly one wheel and one source distribution in "
                f"{distribution_directory}"
            )
        cls.wheel = wheels[0]
        cls.source_distribution = source_distributions[0]

    def test_wheel_contains_cli_and_console_entry_point(self) -> None:
        with zipfile.ZipFile(self.wheel) as archive:
            names = archive.namelist()
            self.assertIn("docling_serve_mps/__init__.py", names)
            self.assertIn("docling_serve_mps/cli.py", names)
            entry_points = [
                name for name in names if name.endswith(".dist-info/entry_points.txt")
            ]
            self.assertEqual(len(entry_points), 1)
            contents = archive.read(entry_points[0]).decode("utf-8")

        self.assertIn("[console_scripts]", contents)
        self.assertIn(
            "docling-serve-mps = docling_serve_mps.cli:main",
            contents,
        )

    def test_sdist_contains_source_workflow_and_tests(self) -> None:
        expected_suffixes = {
            "/LICENSE",
            "/README.md",
            "/pyproject.toml",
            "/service.env",
            "/service.sh",
            "/src/docling_serve_mps/cli.py",
            "/tests/test_cli.py",
            "/tests/test_dist.py",
            "/tests/test_service.sh",
            "/uv.lock",
        }
        with tarfile.open(self.source_distribution, "r:gz") as archive:
            names = archive.getnames()

        for suffix in expected_suffixes:
            self.assertTrue(
                any(name.endswith(suffix) for name in names),
                f"source distribution is missing {suffix}",
            )


if __name__ == "__main__":
    unittest.main()
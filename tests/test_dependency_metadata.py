import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback path.
    tomllib = None


REPO_DIR = Path(__file__).resolve().parents[1]


class DependencyMetadataTests(unittest.TestCase):
    @unittest.skipIf(tomllib is None, "tomllib is unavailable in this Python runtime")
    def test_required_dependencies_match_requirements_txt(self):
        pyproject = tomllib.loads((REPO_DIR / "pyproject.toml").read_text(encoding="utf-8"))
        required = set(pyproject["project"]["dependencies"])
        requirements = {
            line.strip()
            for line in (REPO_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertEqual(required, requirements)

    @unittest.skipIf(tomllib is None, "tomllib is unavailable in this Python runtime")
    def test_aesthetic_predictor_is_optional_extra(self):
        pyproject = tomllib.loads((REPO_DIR / "pyproject.toml").read_text(encoding="utf-8"))
        optional = pyproject["project"]["optional-dependencies"]

        self.assertIn("aesthetic", optional)
        self.assertEqual(["aesthetic-predictor-v2-5"], optional["aesthetic"])


if __name__ == "__main__":
    unittest.main()

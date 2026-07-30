import re
import subprocess
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback path.
    tomllib = None


REPO_DIR = Path(__file__).resolve().parents[1]


def _load_pyproject():
    return tomllib.loads((REPO_DIR / "pyproject.toml").read_text(encoding="utf-8"))


def _git_paths(*arguments):
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in completed.stdout.splitlines() if line}


class DependencyMetadataTests(unittest.TestCase):
    @unittest.skipIf(tomllib is None, "tomllib is unavailable in this Python runtime")
    def test_required_dependencies_match_requirements_txt(self):
        pyproject = _load_pyproject()
        required = set(pyproject["project"]["dependencies"])
        requirements = {
            line.strip()
            for line in (REPO_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertEqual(required, requirements)

    @unittest.skipIf(tomllib is None, "tomllib is unavailable in this Python runtime")
    def test_aesthetic_predictor_is_optional_extra(self):
        pyproject = _load_pyproject()
        optional = pyproject["project"]["optional-dependencies"]

        self.assertIn("aesthetic", optional)
        self.assertEqual(["aesthetic-predictor-v2-5"], optional["aesthetic"])

    @unittest.skipIf(tomllib is None, "tomllib is unavailable in this Python runtime")
    def test_python_floor_matches_accepted_host_policy(self):
        pyproject = _load_pyproject()

        self.assertEqual(">=3.10", pyproject["project"].get("requires-python"))

    @unittest.skipIf(tomllib is None, "tomllib is unavailable in this Python runtime")
    def test_comfyui_floor_matches_accepted_host_policy(self):
        pyproject = _load_pyproject()

        self.assertEqual(
            ">=0.22.3",
            pyproject["tool"]["comfy"].get("requires-comfyui"),
        )

    @unittest.skipIf(tomllib is None, "tomllib is unavailable in this Python runtime")
    def test_frontend_dependency_and_force_includes_remain_absent(self):
        pyproject_path = REPO_DIR / "pyproject.toml"
        pyproject = _load_pyproject()
        dependencies = pyproject["project"]["dependencies"]

        self.assertFalse(
            any(
                dependency.startswith("comfyui-frontend-package")
                for dependency in dependencies
            )
        )
        self.assertEqual([], pyproject["tool"]["comfy"].get("includes"))
        self.assertIsNone(
            re.search(
                r"""["']?requires-comfyui["']?\s*=\s*["']>=1\.0\.0["']""",
                pyproject_path.read_text(encoding="utf-8"),
            ),
            "the stale ComfyUI 1.0 compatibility example must be removed",
        )

    def test_registry_archive_boundary_is_deterministic_and_public_safe(self):
        comfyignore_path = REPO_DIR / ".comfyignore"
        self.assertTrue(
            comfyignore_path.is_file(),
            ".comfyignore must define the Registry archive boundary",
        )

        tracked = _git_paths("ls-files")
        excluded = _git_paths(
            "ls-files",
            "--cached",
            "--ignored",
            "--exclude-from=.comfyignore",
        )
        candidate_archive = tracked - excluded
        expected_development_only = {
            path
            for path in tracked
            if path.startswith((".github/", "scripts/", "tests/"))
            or path
            in {
                ".gitattributes",
                ".gitignore",
                ".pre-commit-config.yaml",
            }
        }
        expected_help_paths = {
            "web/docs/AddTextToImage.md",
            "web/docs/AdvancedImageSaver.md",
            "web/docs/AdvancedTextFilter.md",
            "web/docs/ImageCropper.md",
            "web/docs/LoadImageBatch.md",
            "web/docs/ResizeImageAdvanced.md",
            "web/docs/TextStorageReader.md",
            "web/docs/TextStorageWriter.md",
        }
        required_archive_paths = {
            "__init__.py",
            "advanced_text_filter.py",
            "text_input.py",
            "text_scraper.py",
            "text_storage.py",
            "wildcards.py",
            "simple_eval.py",
            "add_text_to_image.py",
            "font_manager.py",
            "advanced_image_saver.py",
            "image_cropper.py",
            "mask_nodes.py",
            "Image_concat_advanced.py",
            "load_image_batch.py",
            "resize_image_advanced.py",
            "pyproject.toml",
            "requirements.txt",
            "LICENSE",
            "README.md",
            "README.zh-TW.md",
            "examples/advanced_text_filter.png",
            "fonts/.gitkeep",
            "text_storage/.gitkeep",
            "wildcards/.gitkeep",
            "wildcards/example_format.txt",
            *expected_help_paths,
        }

        self.assertEqual(expected_development_only, excluded)
        self.assertTrue(required_archive_paths.issubset(candidate_archive))
        self.assertTrue(expected_development_only.isdisjoint(candidate_archive))
        self.assertEqual(
            expected_help_paths,
            {
                path
                for path in candidate_archive
                if path.startswith("web/docs/")
            },
        )

        forbidden_prefixes = (
            ".planning/",
            "reference/",
            ".sessions/",
            ".tmp/",
            ".venv/",
        )
        self.assertFalse(
            any(path.startswith(forbidden_prefixes) for path in tracked),
            "internal or local-runtime paths must never enter Git tracking",
        )
        self.assertFalse(
            any(
                path.startswith("text_storage/") and path != "text_storage/.gitkeep"
                for path in candidate_archive
            ),
            "user Text Storage content must not enter the Registry archive",
        )


if __name__ == "__main__":
    unittest.main()

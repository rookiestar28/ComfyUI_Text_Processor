import json
import re
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]

EXPECTED_WIDGETS = [
    {"name": "value", "type": "STRING", "transport": "canonical_decimal"},
    {"name": "seed_width", "type": "COMBO"},
    {"name": "timing", "type": "COMBO"},
    {"name": "queue_action", "type": "COMBO"},
    {"name": "distribution", "type": "COMBO"},
    {"name": "last_seed", "type": "STRING", "transport": "canonical_decimal"},
]


def _read_json(relative_path):
    return json.loads(_read_text(relative_path))


def _read_text(relative_path):
    path = REPO_DIR / relative_path
    if not path.is_file():
        raise AssertionError(f"required T07 artifact is missing: {relative_path}")
    return path.read_text(encoding="utf-8")


class FrontendHarnessContractTests(unittest.TestCase):
    def test_package_contract_is_private_pinned_and_lifecycle_free(self):
        package = _read_json("package.json")

        self.assertTrue(package["private"])
        self.assertEqual("module", package["type"])
        self.assertEqual({">=18": True}, {package["engines"]["node"]: True})
        self.assertEqual("playwright test", package["scripts"]["test"])
        self.assertEqual(
            {"@playwright/test": "1.62.1"},
            package["devDependencies"],
        )

        forbidden_lifecycle_scripts = {
            "preinstall",
            "install",
            "postinstall",
            "prepare",
            "prepublish",
            "prepack",
            "postpack",
        }
        self.assertTrue(
            forbidden_lifecycle_scripts.isdisjoint(package.get("scripts", {})),
            "npm lifecycle scripts are forbidden",
        )

        package_lock = _read_json("package-lock.json")
        self.assertEqual(3, package_lock["lockfileVersion"])
        root_package = package_lock["packages"][""]
        self.assertTrue(root_package["devDependencies"]["@playwright/test"].startswith("1.62.1"))
        self.assertEqual(">=18", root_package["engines"]["node"])

    def test_future_global_random_seed_contract_is_exact(self):
        contract = _read_json("tests/fixtures/global_random_seed_contract_v1.json")

        self.assertEqual(1, contract["schema_version"])
        self.assertEqual("Global_RandomSeed", contract["node_id"])
        self.assertEqual("Global Random Seed", contract["display_name"])
        self.assertEqual("ComfyUI Text Processor/Logic", contract["category"])
        self.assertEqual("v1", contract["node_api"])
        self.assertTrue(contract["output_node"])
        self.assertEqual(EXPECTED_WIDGETS, contract["widgets"])
        self.assertEqual(
            [{"index": 0, "type": "INT", "name": "applied_seed"}],
            contract["outputs"],
        )
        self.assertEqual("uint32", contract["seed_width"]["default"])
        self.assertEqual(
            {
                "uint32": {"minimum": "0", "maximum": "4294967295"},
                "uint64": {"minimum": "0", "maximum": "18446744073709551615"},
            },
            contract["seed_width"]["profiles"],
        )
        self.assertEqual(
            {
                "encoding": "canonical_unsigned_decimal_string",
                "javascript_safe_maximum": "9007199254740991",
                "unsafe_numeric_widget_policy": "leave_unchanged",
            },
            contract["browser_transport"],
        )

    def test_playwright_and_generated_artifacts_have_explicit_boundaries(self):
        config = _read_text("playwright.config.mjs")
        self.assertIn("workers: 1", config)
        self.assertIn("headless: true", config)
        self.assertIn('testDir: "./tests/frontend"', config)
        self.assertNotIn("webServer", config)

        gitattributes = (REPO_DIR / ".gitattributes").read_text(encoding="utf-8")
        self.assertRegex(gitattributes, r"(?m)^\*\.sh text eol=lf$")

        gitignore = (REPO_DIR / ".gitignore").read_text(encoding="utf-8")
        for ignored in (
            "node_modules/",
            "playwright-report/",
            "test-results/",
            ".cache/",
            ".tmp/",
        ):
            self.assertIn(ignored, gitignore)

        comfyignore = (REPO_DIR / ".comfyignore").read_text(encoding="utf-8")
        for excluded in (
            "package.json",
            "package-lock.json",
            "playwright.config.mjs",
        ):
            self.assertRegex(comfyignore, rf"(?m)^{re.escape(excluded)}$")

    def test_sops_and_full_test_runners_require_frontend_lane(self):
        test_sop = (REPO_DIR / "tests/TEST_SOP.md").read_text(encoding="utf-8")
        notice = (REPO_DIR / "tests/E2E_TESTING_NOTICE.md").read_text(encoding="utf-8")
        e2e_sop = (REPO_DIR / "tests/E2E_TESTING_SOP.md").read_text(encoding="utf-8")

        for document in (test_sop, notice, e2e_sop):
            self.assertIn("npm test", document)
            self.assertIn("Node.js 18+", document)
            self.assertNotIn(
                "no tracked `package.json`",
                document.lower(),
            )

        windows_runner = (
            REPO_DIR / "scripts/run_full_tests_windows.ps1"
        ).read_text(encoding="utf-8")
        linux_runner = (
            REPO_DIR / "scripts/run_full_tests_linux.sh"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "Get-Command node -ErrorAction SilentlyContinue",
            windows_runner,
        )
        self.assertIn('@("npm", "test")', windows_runner)
        self.assertIn("npm test", linux_runner)
        for runner in (windows_runner, linux_runner):
            self.assertIn("node", runner.lower())
            self.assertIn("18", runner)

    def test_f18_adds_only_the_frozen_runtime_javascript_and_product_node(self):
        runtime_javascript = sorted((REPO_DIR / "web").rglob("*.js"))
        self.assertEqual(
            [REPO_DIR / "web" / "global_random_seed.js"],
            runtime_javascript,
        )

        node_contracts = _read_json("tests/fixtures/node_contracts_v1.json")
        self.assertEqual(18, len(node_contracts["nodes"]))
        self.assertIn("Global_RandomSeed", node_contracts["nodes"])


if __name__ == "__main__":
    unittest.main()

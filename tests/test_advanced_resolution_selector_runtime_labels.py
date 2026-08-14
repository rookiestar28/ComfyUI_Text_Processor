import json
import re
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
EXTENSION_PATH = REPO_DIR / "web" / "advanced_resolution_selector.js"
FIXTURE_PATH = (
    REPO_DIR
    / "tests"
    / "fixtures"
    / "advanced_resolution_selector_runtime_labels_v1.json"
)


class AdvancedResolutionRuntimeLabelContractTests(unittest.TestCase):
    def test_runtime_fixture_pins_both_supported_host_tiers(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(1, fixture["schema_version"])
        self.assertEqual(
            "ComfyUI.TextProcessor.AdvancedResolutionSelectorRuntimeLabels",
            fixture["extension_name"],
        )
        self.assertEqual("TP_AdvancedResolutionSelector", fixture["node_id"])
        self.assertEqual("tp_advanced_resolution", fixture["payload_key"])
        self.assertEqual(
            {"desktop_floor", "current"},
            set(fixture["tiers"]),
        )
        for tier in fixture["tiers"].values():
            self.assertEqual(
                ["setDirtyCanvas", "node:slot-label:changed"],
                tier["refresh"],
            )

    def test_runtime_extension_uses_scoped_safe_surfaces_only(self):
        source = EXTENSION_PATH.read_text(encoding="utf-8")
        for required in (
            "app.registerExtension",
            "beforeRegisterNodeDef",
            "TP_AdvancedResolutionSelector",
            "tp_advanced_resolution",
            "WeakMap",
            "Number.isSafeInteger",
            "onExecuted",
            "onConfigure",
            "onSerialize",
            "setDirtyCanvas",
            "node:slot-label:changed",
        ):
            self.assertIn(required, source)

        forbidden = (
            "innerHTML",
            "fetch(",
            "XMLHttpRequest",
            "queuePrompt",
            "graphToPrompt",
            "localStorage",
            "sessionStorage",
            "eval(",
            "console.",
            "document.",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

        self.assertNotRegex(source, re.compile(r"(?i)secret|token|cookie|authorization"))

    def test_public_help_describes_last_successful_result_and_degradation(self):
        help_text = (
            REPO_DIR / "web" / "docs" / "TP_AdvancedResolutionSelector.md"
        ).read_text(encoding="utf-8")
        readme_text = (REPO_DIR / "README.md").read_text(encoding="utf-8")
        for text in (help_text, readme_text):
            self.assertIn("last successful", text.lower())
            self.assertIn("static", text.lower())
            self.assertIn("legacy", text.lower())
            self.assertIn("21:9", text)
        normalized_help = " ".join(help_text.split())
        self.assertIn(
            "`1:1`, `9:7`, `4:3`, `19:13`, `3:2`, `7:4`, and `16:9`",
            normalized_help,
        )
        self.assertNotIn("`16:9` followed by `portrait`", readme_text)
        self.assertIn("`7:4` followed by `portrait`", readme_text)
        self.assertNotRegex(
            help_text,
            re.compile(
                r"(?i)(?:\.planning|reference[/\\]|ROADMAP\.md|command[_ -]?log|"
                r"implementation[_ -]?record|api[_ -]?key|authorization:|cookie:|private[_ -]?key)"
            ),
        )


if __name__ == "__main__":
    unittest.main()

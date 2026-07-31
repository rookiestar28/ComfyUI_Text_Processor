import json
import re
import unittest
from pathlib import Path

try:
    from test_host_compatibility_contracts import (
        NODE_CONTRACTS_PATH,
        PackageImportContext,
        _normalized_package_contracts,
    )
except ModuleNotFoundError:
    from tests.test_host_compatibility_contracts import (
        NODE_CONTRACTS_PATH,
        PackageImportContext,
        _normalized_package_contracts,
    )


REPO_DIR = Path(__file__).resolve().parents[1]
HELP_CONTRACT_PATH = (
    REPO_DIR / "tests" / "fixtures" / "node_help_host_contracts_v1.json"
)
FORBIDDEN_PUBLIC_HELP_TEXT = re.compile(
    r"(?ix)"
    r"(?:"
    r"\.planning"
    r"|reference[/\\]"
    r"|ROADMAP\.md"
    r"|command[ _-]?log"
    r"|implementation[ _-]?record"
    r"|(?:^|\W)(?:G03|T06|F15|D02|F16|G04|F17|DOC03|T07|F18|DOC04)(?:\W|$)"
    r"|[A-Z]:\\"
    r"|/home/"
    r"|api[_ -]?key"
    r"|authorization:"
    r"|cookie:"
    r"|private[ _-]?key"
    r"|<script"
    r")"
)


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _visible_inputs(input_types):
    for group_name in ("required", "optional"):
        for input_name, input_spec in input_types.get(group_name, {}).items():
            options = (
                input_spec[1]
                if isinstance(input_spec, (tuple, list))
                and len(input_spec) > 1
                and isinstance(input_spec[1], dict)
                else {}
            )
            yield group_name, input_name, options


class NodeHelpContractTests(unittest.TestCase):
    def load_help_contract(self):
        contract = _load_json(HELP_CONTRACT_PATH)
        self.assertEqual(1, contract.get("schema_version"))
        return contract

    def test_all_user_visible_inputs_have_non_empty_tooltips(self):
        contract = self.load_help_contract()

        with PackageImportContext() as package:
            missing = []
            visible_count = 0
            for node_id, node_class in package.NODE_CLASS_MAPPINGS.items():
                for group_name, input_name, options in _visible_inputs(
                    node_class.INPUT_TYPES()
                ):
                    visible_count += 1
                    tooltip = options.get("tooltip")
                    if not isinstance(tooltip, str) or not tooltip.strip():
                        missing.append(f"{node_id}.{group_name}.{input_name}")

        self.assertEqual(contract["expected_node_count"], len(package.NODE_CLASS_MAPPINGS))
        self.assertEqual(contract["expected_visible_input_count"], visible_count)
        self.assertEqual([], missing, f"missing input tooltips: {missing}")

    def test_hidden_inputs_are_the_only_approved_exclusions(self):
        contract = self.load_help_contract()

        with PackageImportContext() as package:
            actual_hidden = {
                node_id: list(node_class.INPUT_TYPES().get("hidden", {}))
                for node_id, node_class in package.NODE_CLASS_MAPPINGS.items()
                if node_class.INPUT_TYPES().get("hidden")
            }

        self.assertEqual(contract["excluded_hidden_inputs"], actual_hidden)

    def test_tooltip_metadata_preserves_frozen_v1_contract(self):
        frozen = _load_json(NODE_CONTRACTS_PATH)

        with PackageImportContext() as package:
            actual = _normalized_package_contracts(package)

        self.assertEqual(frozen["nodes"], actual)

    def test_two_tier_help_transport_is_pinned_and_identical(self):
        contract = self.load_help_contract()
        tiers = contract["tiers"]
        self.assertEqual({"desktop_floor", "current_observation"}, set(tiers))

        floor = tiers["desktop_floor"]
        current = tiers["current_observation"]
        transport_fields = {
            "help_lookup_blob_short",
            "generic_help_blob_short",
            "v1_input_transform_blob_short",
            "localized_lookup",
            "fallback_lookup",
            "extension_route",
        }
        for field in transport_fields:
            with self.subTest(field=field):
                self.assertEqual(floor[field], current[field])

        self.assertEqual("0.22.3", floor["core_version"])
        self.assertEqual("1.43.18", floor["frontend_version"])
        self.assertEqual("0.29.0", current["core_version"])
        self.assertEqual("1.49.1", current["frontend_version"])

    def test_web_directory_and_exact_rich_help_set(self):
        contract = self.load_help_contract()

        with PackageImportContext() as package:
            self.assertEqual(
                contract["web_directory"],
                getattr(package, "WEB_DIRECTORY", None),
            )

        web_root = (REPO_DIR / contract["web_directory"]).resolve()
        self.assertTrue(web_root.is_relative_to(REPO_DIR.resolve()))
        docs_dir = web_root / "docs"
        actual = {
            path.stem
            for path in docs_dir.glob("*.md")
            if path.is_file()
        }
        self.assertEqual(set(contract["rich_help_node_ids"]), actual)

    def test_rich_help_covers_selected_inputs_and_is_public_safe(self):
        contract = self.load_help_contract()
        docs_dir = REPO_DIR / contract["web_directory"] / "docs"

        with PackageImportContext() as package:
            for node_id in contract["rich_help_node_ids"]:
                with self.subTest(node_id=node_id):
                    doc_path = docs_dir / f"{node_id}.md"
                    text = doc_path.read_text(encoding="utf-8")
                    display_name = package.NODE_DISPLAY_NAME_MAPPINGS[node_id]
                    self.assertTrue(text.startswith(f"# {display_name}\n"))
                    self.assertIn("\n## Inputs\n", text)
                    self.assertIn("\n## Behavior\n", text)
                    self.assertIsNone(FORBIDDEN_PUBLIC_HELP_TEXT.search(text))

                    input_names = [
                        input_name
                        for _group, input_name, _options in _visible_inputs(
                            package.NODE_CLASS_MAPPINGS[node_id].INPUT_TYPES()
                        )
                    ]
                    for input_name in input_names:
                        self.assertIn(f"`{input_name}`", text)


if __name__ == "__main__":
    unittest.main()

import importlib
import inspect
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "tests" / "fixtures" / "split_string_contract_v1.json"
FORBIDDEN_PUBLIC_TEXT = re.compile(
    r"(?i)(?:[A-Z]:\\|/home/|\.planning|reference/|https?://|api[_-]?key|cookie|secret|token)"
)


def _contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _module():
    return importlib.import_module("split_string")


class SplitStringContractTests(unittest.TestCase):
    def test_fixture_is_complete_and_public_safe(self):
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        contract = json.loads(text)

        self.assertEqual(1, contract["schema_version"])
        self.assertEqual("clean_room_behavioral_reimplementation", contract["provenance"])
        self.assertEqual(10, len(contract["behavior_vectors"]))
        self.assertEqual(1, len(contract["error_vectors"]))
        self.assertIsNone(FORBIDDEN_PUBLIC_TEXT.search(text))

    def test_exact_public_identity_and_schema(self):
        module = _module()
        node_class = module.SplitString
        expected = _contract()["node"]
        required = node_class.INPUT_TYPES()["required"]

        self.assertEqual(["text", "delimiter"], list(required))
        for input_contract in expected["inputs"]:
            input_type, options = required[input_contract["name"]]
            self.assertEqual(input_contract["type"], input_type)
            self.assertEqual(input_contract["default"], options["default"])
            self.assertEqual(input_contract["multiline"], options["multiline"])
            self.assertEqual(input_contract["tooltip"], options["tooltip"])

        self.assertEqual(("STRING", "STRING"), node_class.RETURN_TYPES)
        self.assertEqual(("left", "right"), node_class.RETURN_NAMES)
        self.assertEqual(
            tuple(output["tooltip"] for output in expected["outputs"]),
            node_class.OUTPUT_TOOLTIPS,
        )
        self.assertEqual(expected["function"], node_class.FUNCTION)
        self.assertEqual(expected["category"], node_class.CATEGORY)
        self.assertEqual(expected["description"], node_class.DESCRIPTION)
        self.assertEqual(expected["search_aliases"], node_class.SEARCH_ALIASES)
        self.assertFalse(getattr(node_class, "OUTPUT_NODE", False))
        self.assertFalse(hasattr(node_class, "IS_CHANGED"))

    def test_behavior_vectors_split_once_without_normalization(self):
        node = _module().SplitString()
        for vector in _contract()["behavior_vectors"]:
            with self.subTest(vector=vector["id"]):
                actual = node.split_string(vector["text"], vector["delimiter"])
                self.assertEqual(tuple(vector["expected"]), actual)
                self.assertEqual(2, len(actual))
                self.assertTrue(all(isinstance(value, str) for value in actual))
                self.assertEqual(actual, node.split_string(vector["text"], vector["delimiter"]))

    def test_empty_delimiter_raises_static_content_free_error(self):
        node = _module().SplitString()
        vector = _contract()["error_vectors"][0]

        with self.assertRaisesRegex(ValueError, r"^delimiter must not be empty$") as raised:
            node.split_string(vector["text"], vector["delimiter"])
        self.assertNotIn(vector["text"], str(raised.exception))

    def test_behavior_contract_kills_common_split_mutations(self):
        contract = _contract()

        def assert_candidate(candidate):
            for vector in contract["behavior_vectors"]:
                self.assertEqual(
                    tuple(vector["expected"]),
                    candidate(vector["text"], vector["delimiter"]),
                )
            error = contract["error_vectors"][0]
            with self.assertRaisesRegex(ValueError, r"^delimiter must not be empty$"):
                candidate(error["text"], error["delimiter"])

        def split_last(text, delimiter):
            if delimiter == "":
                raise ValueError("delimiter must not be empty")
            parts = text.rsplit(delimiter, 1)
            return (text, "") if len(parts) == 1 else (parts[0], parts[1])

        def retain_delimiter(text, delimiter):
            if delimiter == "":
                raise ValueError("delimiter must not be empty")
            left, found, right = text.partition(delimiter)
            return (text, "") if not found else (left + found, right)

        def normalize_whitespace(text, delimiter):
            if delimiter == "":
                raise ValueError("delimiter must not be empty")
            parts = text.split(delimiter, 1)
            return tuple(value.strip() for value in (parts if len(parts) == 2 else (text, "")))

        def wrong_absent_output(text, delimiter):
            if delimiter == "":
                raise ValueError("delimiter must not be empty")
            parts = text.split(delimiter, 1)
            return ("", text) if len(parts) == 1 else (parts[0], parts[1])

        def accepts_empty_delimiter(text, delimiter):
            if delimiter == "":
                return text, ""
            parts = text.split(delimiter, 1)
            return (text, "") if len(parts) == 1 else (parts[0], parts[1])

        for name, mutant in (
            ("split_last", split_last),
            ("retain_delimiter", retain_delimiter),
            ("normalize_whitespace", normalize_whitespace),
            ("wrong_absent_output", wrong_absent_output),
            ("accepts_empty_delimiter", accepts_empty_delimiter),
        ):
            with self.subTest(mutant=name), self.assertRaises(AssertionError):
                assert_candidate(mutant)

    def test_mapping_is_package_scoped_and_coexists_with_raw_external_id(self):
        module = _module()
        self.assertEqual({"TP_SplitString": module.SplitString}, module.NODE_CLASS_MAPPINGS)
        self.assertEqual({"TP_SplitString": "Split String"}, module.NODE_DISPLAY_NAME_MAPPINGS)
        self.assertNotIn("SplitString", module.NODE_CLASS_MAPPINGS)
        self.assertNotIn("SplitStringByDelimiter", module.NODE_CLASS_MAPPINGS)

        external_class = object()
        combined = {"SplitString": external_class, **module.NODE_CLASS_MAPPINGS}
        self.assertIs(external_class, combined["SplitString"])
        self.assertIs(module.SplitString, combined["TP_SplitString"])

    def test_module_is_pure_and_compile_documentation_surfaces_include_it(self):
        module = _module()
        source = inspect.getsource(module)
        for forbidden in (
            "requests",
            "urllib",
            "subprocess",
            "open(",
            "logging",
            "random",
            "IS_CHANGED",
            "SplitStringByDelimiter",
        ):
            self.assertNotIn(forbidden, source)

        for path in (
            ROOT / ".pre-commit-config.yaml",
            ROOT / "tests" / "TEST_SOP.md",
            ROOT / "tests" / "E2E_TESTING_SOP.md",
        ):
            self.assertIn("split_string.py", path.read_text(encoding="utf-8"), path.name)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for required in (
            "20 production nodes",
            "155 visible inputs",
            "### Split String",
            "`left`",
            "`right`",
            "delimiter must not be empty",
        ):
            self.assertIn(required, readme)


if __name__ == "__main__":
    unittest.main()

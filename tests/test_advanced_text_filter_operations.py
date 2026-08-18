import copy
import io
import json
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import advanced_text_filter as advanced_text_filter_module
from advanced_text_filter import AdvancedTextFilter


REPO_DIR = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_DIR / "tests" / "fixtures" / "advanced_text_filter_operation_contract_v1.json"
TRIPLE_BACKTICK = chr(96) * 3
CODE_OPERATION = f"LLM: extract code block ({TRIPLE_BACKTICK})"
JSON_OPERATION = "LLM: extract JSON object ({...})"
BASE_TEXT = "LEFT CENTER RIGHT"
CANARY = "SYNTHETIC_F27_CANARY"


class AdvancedTextFilterOperationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.node = AdvancedTextFilter()

    def run_node(
        self,
        operation,
        *,
        text=BASE_TEXT,
        start="",
        end="",
        optional="",
        replacement_rules="",
        use_regex=False,
        case_conversion="disabled",
        policy="return original text",
        external_text=None,
        concat_mode="disabled",
        replace_with_text="REPLACED",
    ):
        return self.node.process(
            text=text,
            concat_mode=concat_mode,
            operation=operation,
            start_text=start,
            end_text=end,
            optional_text_input=optional,
            replace_with_text=replace_with_text,
            use_regex=use_regex,
            case_conversion=case_conversion,
            if_not_found=policy,
            external_text=external_text,
            replacement_rules=replacement_rules,
        )

    def missing_kwargs(self, operation):
        if operation == "find all (extract) (use optional_text)":
            return {"optional": "NO_MATCH"}
        if operation in {
            "find and remove (use optional_text)",
            "find and replace (use optional_text, replace_with_text)",
        }:
            return {"optional": "NO_MATCH"}
        if operation == "batch replace (use replacement_rules)":
            return {"replacement_rules": "NO_MATCH -> REPLACED"}
        if operation in {"extract between", "remove between"}:
            return {"start": "NO_START", "end": "NO_END"}
        if "start text" in operation:
            return {"start": "NO_START"}
        if operation == CODE_OPERATION:
            return {"text": "plain response"}
        if operation == JSON_OPERATION:
            return {"text": "plain response"}
        raise AssertionError(f"missing case not defined for {operation}")

    @staticmethod
    def missing_reason(operation):
        if operation == "batch replace (use replacement_rules)":
            return "no batch rule matched"
        if operation == CODE_OPERATION:
            return "code block not found"
        if operation == JSON_OPERATION:
            return "valid JSON object not found"
        return "search pattern not found" if operation.startswith("find") else "start boundary not found"

    def assert_missing_result(self, operation, use_regex):
        kwargs = self.missing_kwargs(operation)
        original = kwargs.get("text", BASE_TEXT)
        expected_original = (original, "")
        expected_empty = ("", original)
        for policy, expected in (
            ("return original text", expected_original),
            ("return empty string", expected_empty),
        ):
            with self.subTest(operation=operation, use_regex=use_regex, policy=policy):
                self.assertEqual(
                    expected,
                    self.run_node(operation, use_regex=use_regex, policy=policy, **kwargs),
                )

        with self.subTest(operation=operation, use_regex=use_regex, policy="trigger error"):
            with self.assertRaisesRegex(
                ValueError,
                rf"^\[AdvancedTextFilter\] {re.escape(self.missing_reason(operation))}$",
            ) as raised:
                self.run_node(operation, use_regex=use_regex, policy="trigger error", **kwargs)
            self.assertNotIn(CANARY, str(raised.exception))

    def test_node_identity_and_operation_fixture(self):
        node_spec = self.contract["node"]
        input_types = self.node.INPUT_TYPES()
        self.assertEqual(node_spec["required_inputs"], list(input_types["required"]))
        self.assertEqual(node_spec["optional_inputs"], list(input_types["optional"]))
        self.assertEqual(node_spec["return_types"], list(self.node.RETURN_TYPES))
        self.assertEqual(node_spec["return_names"], list(self.node.RETURN_NAMES))
        self.assertEqual(node_spec["function"], self.node.FUNCTION)
        self.assertEqual(node_spec["category"], self.node.CATEGORY)
        self.assertEqual(
            node_spec["operation_modes"],
            list(input_types["required"]["operation"][0]),
        )
        self.assertEqual(
            node_spec["if_not_found_policies"],
            list(input_types["required"]["if_not_found"][0]),
        )
        self.assertEqual(17, len(node_spec["operation_modes"]))
        self.assertEqual(3, len(node_spec["if_not_found_policies"]))

    def test_missing_policy_matrix_literal_and_regex(self):
        groups = self.contract["missing_aware_operation_groups"]
        operations = groups["extraction_like"] + groups["transform_like"]
        self.assertEqual(12, len(operations))
        for operation in operations:
            self.assert_missing_result(operation, use_regex=False)
            self.assert_missing_result(operation, use_regex=True)

    def test_empty_required_inputs_use_normalized_policy(self):
        cases = (
            (
                "find all (extract) (use optional_text)",
                {"optional": ""},
                "search pattern is missing",
            ),
            (
                "find and replace (use optional_text, replace_with_text)",
                {"optional": ""},
                "search pattern is missing",
            ),
            (
                "batch replace (use replacement_rules)",
                {"replacement_rules": ""},
                "replacement rules are missing",
            ),
            (
                "extract before start text",
                {"start": ""},
                "start boundary is missing",
            ),
            (
                "extract between",
                {"start": "", "end": ""},
                "start or end boundary is missing",
            ),
        )
        expected_original = tuple(self.contract["fallback_contract"]["return_original_text"])
        expected_empty = tuple(self.contract["fallback_contract"]["return_empty_string"])
        for operation, kwargs, reason in cases:
            with self.subTest(operation=operation):
                self.assertEqual(
                    expected_original,
                    self.run_node(operation, policy="return original text", **kwargs),
                )
                self.assertEqual(
                    expected_empty,
                    self.run_node(operation, policy="return empty string", **kwargs),
                )
                with self.assertRaisesRegex(
                    ValueError,
                    rf"^\[AdvancedTextFilter\] {re.escape(reason)}$",
                ):
                    self.run_node(operation, policy="trigger error", **kwargs)

    def test_empty_text_uses_normalized_policy_for_missing_matches(self):
        for operation in self.contract["missing_aware_operation_groups"]["extraction_like"]:
            with self.subTest(operation=operation):
                kwargs = self.missing_kwargs(operation)
                kwargs["text"] = ""
                self.assertEqual(
                    ("", ""),
                    self.run_node(operation, policy="return original text", **kwargs),
                )
                self.assertEqual(
                    ("", ""),
                    self.run_node(operation, policy="return empty string", **kwargs),
                )

    def test_missing_policy_uses_preprocessed_original(self):
        expected = tuple(self.contract["preprocessing_contract"]["expected"])
        self.assertEqual(
            expected,
            self.run_node(
                "find and replace (use optional_text, replace_with_text)",
                text="needle",
                optional="NO_MATCH",
                external_text="prefix ",
                concat_mode="prepend_external_text",
                case_conversion="to UPPERCASE",
            ),
        )
        self.assertEqual(
            ("", "PREFIX NEEDLE"),
            self.run_node(
                "find all (extract) (use optional_text)",
                text="needle",
                optional="NO_MATCH",
                external_text="prefix ",
                concat_mode="prepend_external_text",
                case_conversion="to UPPERCASE",
                policy="return empty string",
            ),
        )

    def test_marker_ownership_literal_regex_and_multiline(self):
        marker = self.contract["marker_contract"]
        expected = {
            key: tuple(value)
            for key, value in marker["expected"].items()
        }
        for operation, result in expected.items():
            with self.subTest(operation=operation, mode="literal"):
                self.assertEqual(
                    result,
                    self.run_node(
                        operation,
                        text=marker["literal_input"],
                        start=marker["literal_marker"],
                    ),
                )
            with self.subTest(operation=operation, mode="regex"):
                self.assertEqual(
                    result,
                    self.run_node(
                        operation,
                        text=marker["regex_input"],
                        start=marker["regex_marker"],
                        use_regex=True,
                    ),
                )
            with self.subTest(operation=operation, mode="multiline-regex"):
                multiline_expected = (
                    result[0].replace("<MARK>", "<MARK\nVALUE>"),
                    result[1].replace("<MARK>", "<MARK\nVALUE>"),
                )
                self.assertEqual(
                    multiline_expected,
                    self.run_node(
                        operation,
                        text=marker["multiline_input"],
                        start=marker["multiline_regex_marker"],
                        use_regex=True,
                    ),
                )

        for operation, result in marker["between_expected"].items():
            with self.subTest(operation=operation):
                self.assertEqual(
                    tuple(result),
                    self.run_node(
                        operation,
                        text=marker["between_input"],
                        start=marker["between_start"],
                        end=marker["between_end"],
                    ),
                )

    def test_json_extracts_first_valid_nested_object(self):
        contract = self.contract["json_contract"]
        self.assertEqual(
            tuple(contract["first_valid_expected"]),
            self.run_node(JSON_OPERATION, text=contract["first_valid_input"]),
        )
        self.assertEqual(
            tuple(contract["malformed_then_valid_expected"]),
            self.run_node(JSON_OPERATION, text=contract["malformed_then_valid_input"]),
        )
        self.assertEqual(
            tuple(contract["nested_expected"]),
            self.run_node(JSON_OPERATION, text=contract["nested_input"]),
        )

    def test_json_rejects_non_objects_and_non_standard_constants(self):
        for text in (
            "[1, 2]",
            "42",
            '"scalar"',
            *self.contract["json_contract"]["strict_constant_inputs"],
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    ("", text),
                    self.run_node(
                        JSON_OPERATION,
                        text=text,
                        policy="return empty string",
                    ),
                )
                with self.assertRaisesRegex(
                    ValueError,
                    r"^\[AdvancedTextFilter\] valid JSON object not found$",
                ):
                    self.run_node(JSON_OPERATION, text=text, policy="trigger error")

    def test_json_candidate_limit_inspects_1024_and_not_1025(self):
        limit = self.contract["json_contract"]["candidate_limit"]
        raw_decode = json.JSONDecoder.raw_decode

        def run_counted(text):
            calls = []

            def counted(decoder, source, index=0):
                calls.append(index)
                return raw_decode(decoder, source, index)

            with patch.object(json.JSONDecoder, "raw_decode", counted):
                result = self.run_node(
                    JSON_OPERATION,
                    text=text,
                    policy="return empty string",
                )
            return result, calls

        bad = self.contract["json_contract"]["candidate_1024_input_prefix"]
        valid = self.contract["json_contract"]["candidate_1024_valid_suffix"]
        result_1024, calls_1024 = run_counted(bad * (limit - 1) + valid)
        self.assertEqual((valid, bad * (limit - 1)), result_1024)
        self.assertEqual(limit, len(calls_1024))

        result_1025, calls_1025 = run_counted(bad * limit + valid)
        self.assertEqual(("", bad * limit + valid), result_1025)
        self.assertEqual(limit, len(calls_1025))

        long_text = "x" * 100000 + bad * limit
        long_result, long_calls = run_counted(long_text)
        self.assertEqual(("", long_text), long_result)
        self.assertEqual(limit, len(long_calls))

    def test_code_fence_languages_and_ownership(self):
        body = self.contract["fence_contract"]["body"]
        for language in self.contract["fence_contract"]["labeled_languages"]:
            text = f"{TRIPLE_BACKTICK}{language}\n{body}{TRIPLE_BACKTICK}"
            with self.subTest(language=language):
                self.assertEqual((body, ""), self.run_node(CODE_OPERATION, text=text))

        fence_cases = (
            (f"{TRIPLE_BACKTICK}\n{body}{TRIPLE_BACKTICK}", tuple(self.contract["fence_contract"]["unlabeled"])),
            (f"{TRIPLE_BACKTICK}\r\n{body}{TRIPLE_BACKTICK}", tuple(self.contract["fence_contract"]["crlf"])),
            (f"{TRIPLE_BACKTICK}{body}{TRIPLE_BACKTICK}", tuple(self.contract["fence_contract"]["inline"])),
            (
                f"prefix {TRIPLE_BACKTICK}python\n{body}{TRIPLE_BACKTICK} middle "
                f"{TRIPLE_BACKTICK}c++\nSECOND{TRIPLE_BACKTICK} suffix",
                tuple(self.contract["fence_contract"]["multiple"]),
            ),
            (
                f"prefix {TRIPLE_BACKTICK}python\n{body}{TRIPLE_BACKTICK} suffix "
                f"{TRIPLE_BACKTICK}unmatched",
                tuple(self.contract["fence_contract"]["complete_plus_unmatched"]),
            ),
        )
        for text, expected in fence_cases:
            with self.subTest(text=text):
                self.assertEqual(expected, self.run_node(CODE_OPERATION, text=text))

        unmatched = f"prefix {TRIPLE_BACKTICK}unmatched"
        self.assertEqual(
            ("", unmatched),
            self.run_node(CODE_OPERATION, text=unmatched, policy="return empty string"),
        )
        with self.assertRaisesRegex(ValueError, r"^\[AdvancedTextFilter\] code block not found$"):
            self.run_node(CODE_OPERATION, text=unmatched, policy="trigger error")

    def test_markdown_cleanup_preserves_literal_underscores(self):
        markdown = self.contract["markdown_contract"]
        self.assertEqual(
            (markdown["expected"], ""),
            self.run_node("LLM: clean markdown formatting", text=markdown["input"]),
        )
        self.assertEqual(
            (markdown["plain_expected"], ""),
            self.run_node("LLM: clean markdown formatting", text=markdown["plain_input"]),
        )

    def test_diagnostics_are_static_for_regex_and_unexpected_errors(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            invalid_regex = self.run_node(
                "find and replace (use optional_text, replace_with_text)",
                optional="[",
                use_regex=True,
            )
        self.assertEqual(
            (BASE_TEXT, self.contract["safe_reasons"]["invalid_regex"]),
            invalid_regex,
        )
        self.assertIn("[AdvancedTextFilter] Regex Error: invalid regular expression", stdout.getvalue())
        self.assertNotIn(CANARY, stdout.getvalue())

        stdout = io.StringIO()
        with patch.object(
            advanced_text_filter_module.re,
            "subn",
            side_effect=RuntimeError(CANARY),
        ):
            with redirect_stdout(stdout):
                unexpected = self.run_node(
                    "find and replace (use optional_text, replace_with_text)",
                    optional="NEEDLE",
                    use_regex=True,
                )
        self.assertEqual(
            (BASE_TEXT, self.contract["safe_reasons"]["unexpected_error"]),
            unexpected,
        )
        self.assertEqual("[AdvancedTextFilter] Unexpected processing error\n", stdout.getvalue())
        self.assertNotIn(CANARY, stdout.getvalue())

        with self.assertRaisesRegex(
            ValueError,
            r"^\[AdvancedTextFilter\] search pattern not found$",
        ):
            self.run_node(
                "find and remove (use optional_text)",
                optional=CANARY,
                policy="trigger error",
            )

    def test_successful_existing_operations_remain_stable(self):
        self.assertEqual(
            ("LEFT  RIGHT", "CENTER"),
            self.run_node(
                "find and remove (use optional_text)",
                optional=" CENTER ",
            ),
        )
        self.assertEqual(
            ("LEFT CENTER RIGHT", "CENTER"),
            self.run_node(
                "find and replace (use optional_text, replace_with_text)",
                optional="CENTER",
                replace_with_text="CENTER",
            ),
        )
        self.assertEqual(
            ("LEFT MIDDLE RIGHT", ""),
            self.run_node(
                "batch replace (use replacement_rules)",
                replacement_rules="CENTER -> MIDDLE",
            ),
        )
        self.assertEqual(
            ("one\n two", ""),
            self.run_node("remove empty lines", text="one\n\n two\n"),
        )
        self.assertEqual(
            ("one two", ""),
            self.run_node("remove newlines", text="one\n two"),
        )
        self.assertEqual(
            ("one\ntwo", ""),
            self.run_node("strip lines (trim)", text=" one \n two "),
        )
        self.assertEqual(
            ("one\ntwo", ""),
            self.run_node("remove all whitespace (keep newlines)", text=" one \n two "),
        )
        self.assertEqual(
            ("INNER", "A<START><END>Z"),
            self.run_node(
                "extract between",
                text="A<START>INNER<END>Z",
                start="<START>",
                end="<END>",
            ),
        )

    def test_concat_case_and_regex_capture_contracts_remain_stable(self):
        self.assertEqual(
            ("PREFIX NEEDLE", "PREFIX NEEDLE"),
            self.run_node(
                "find and replace (use optional_text, replace_with_text)",
                text="needle",
                optional="PREFIX NEEDLE",
                external_text="prefix ",
                concat_mode="prepend_external_text",
                case_conversion="to UPPERCASE",
                replace_with_text="PREFIX NEEDLE",
            ),
        )
        self.assertEqual(
            ("42\n99", " "),
            self.run_node(
                "find all (extract) (use optional_text)",
                text="id=42 id=99",
                optional=r"id=(\d+)",
                use_regex=True,
            ),
        )

    def test_fixture_mutation_is_detected_by_contract_assertion(self):
        mutated = copy.deepcopy(self.contract)
        mutated["fallback_contract"]["return_empty_string"][0] = "MUTATED"
        actual = self.run_node(
            "find all (extract) (use optional_text)",
            optional="NO_MATCH",
            policy="return empty string",
        )
        self.assertEqual(
            tuple(self.contract["fallback_contract"]["return_empty_string"]),
            actual,
        )
        self.assertNotEqual(tuple(mutated["fallback_contract"]["return_empty_string"]), actual)

    def test_contract_mutations_are_rejected_across_behavior_sections(self):
        cases = (
            (
                "marker",
                ("extract after start text", "LEFT<MARK>RIGHT", "<MARK>"),
                self.contract["marker_contract"]["expected"]["extract after start text"],
                ("MUTATED", "LEFT<MARK>"),
            ),
            (
                "json",
                (JSON_OPERATION, self.contract["json_contract"]["first_valid_input"], None),
                self.contract["json_contract"]["first_valid_expected"],
                ("MUTATED", ""),
            ),
            (
                "fence",
                (CODE_OPERATION, f"{TRIPLE_BACKTICK}python\nBODY{TRIPLE_BACKTICK}", None),
                ("BODY", ""),
                ("MUTATED", ""),
            ),
            (
                "markdown",
                ("LLM: clean markdown formatting", self.contract["markdown_contract"]["input"], None),
                (
                    self.contract["markdown_contract"]["expected"],
                    "",
                ),
                ("MUTATED", ""),
            ),
            (
                "preprocessing",
                (
                    "find and replace (use optional_text, replace_with_text)",
                    self.contract["preprocessing_contract"]["text"],
                    "NO_MATCH",
                ),
                self.contract["preprocessing_contract"]["expected"],
                ("MUTATED", ""),
            ),
        )
        for name, (operation, text, pattern), expected, mutated in cases:
            with self.subTest(section=name):
                if name == "marker":
                    actual = self.run_node(operation, text=text, start=pattern)
                elif name == "json" or name == "fence" or name == "markdown":
                    actual = self.run_node(operation, text=text)
                elif name == "preprocessing":
                    actual = self.run_node(
                        operation,
                        text=text,
                        optional=pattern,
                        external_text=self.contract["preprocessing_contract"]["external_text"],
                        concat_mode=self.contract["preprocessing_contract"]["concat_mode"],
                        case_conversion=self.contract["preprocessing_contract"]["case_conversion"],
                        replace_with_text="REPLACED",
                    )
                else:
                    raise AssertionError(f"unknown mutation section: {name}")
                self.assertEqual(tuple(expected), actual)
                self.assertNotEqual(tuple(mutated), actual)

    def test_fixture_is_canonical_lf_and_archive_excluded(self):
        raw = FIXTURE_PATH.read_bytes()
        self.assertTrue(raw)
        self.assertEqual(10, raw[-1])
        self.assertNotIn(b"\r", raw)

        comfyignore = (REPO_DIR / ".comfyignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("tests/", comfyignore)
        self.assertNotIn(str(FIXTURE_PATH).replace("\\", "/"), comfyignore)

        public_text = (
            (REPO_DIR / "README.md").read_text(encoding="utf-8")
            + (REPO_DIR / "web" / "docs" / "AdvancedTextFilter.md").read_text(encoding="utf-8")
        )
        self.assertIsNone(re.search(r"(?i)(?:\\.planning|reference/docs|F27|[A-Z]:\\\\)", public_text))
        for required_fact in (
            "Missing-match policy",
            "preprocessed input",
            "first valid JSON object",
            "1,024",
            "punctuation-bearing language names",
            "literal underscores inside identifiers",
        ):
            self.assertIn(required_fact, public_text)


if __name__ == "__main__":
    unittest.main()

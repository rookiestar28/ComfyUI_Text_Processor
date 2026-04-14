import unittest

from advanced_text_filter import AdvancedTextFilter


class AdvancedTextFilterNotFoundTests(unittest.TestCase):
    def setUp(self):
        self.node = AdvancedTextFilter()

    def run_node(self, if_not_found, operation="find and replace (use optional_text, replace_with_text)"):
        return self.node.process(
            text="hello world",
            concat_mode="disabled",
            operation=operation,
            start_text="",
            end_text="",
            optional_text_input="missing",
            replace_with_text="replacement",
            use_regex=False,
            case_conversion="disabled",
            if_not_found=if_not_found,
            external_text=None,
            replacement_rules="",
        )

    def test_trigger_error_raises_for_missing_pattern(self):
        with self.assertRaisesRegex(ValueError, "Pattern not found"):
            self.run_node("trigger error")

    def test_return_original_text_keeps_existing_behavior(self):
        self.assertEqual(("hello world", ""), self.run_node("return original text"))

    def test_return_empty_string_keeps_extract_mode_behavior(self):
        result = self.node.process(
            text="hello world",
            concat_mode="disabled",
            operation="find all (extract) (use optional_text)",
            start_text="",
            end_text="",
            optional_text_input="missing",
            replace_with_text="",
            use_regex=False,
            case_conversion="disabled",
            if_not_found="return empty string",
            external_text=None,
            replacement_rules="",
        )

        self.assertEqual(("", "hello world"), result)


if __name__ == "__main__":
    unittest.main()

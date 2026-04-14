import unittest

from advanced_text_filter import AdvancedTextFilter


class AdvancedTextFilterRegexTests(unittest.TestCase):
    def setUp(self):
        self.node = AdvancedTextFilter()

    def run_extract(self, text, pattern):
        return self.node.process(
            text=text,
            concat_mode="disabled",
            operation="find all (extract) (use optional_text)",
            start_text="",
            end_text="",
            optional_text_input=pattern,
            replace_with_text="",
            use_regex=True,
            case_conversion="disabled",
            if_not_found="trigger error",
            external_text=None,
            replacement_rules="",
        )

    def test_regex_extract_without_groups_returns_full_matches(self):
        processed, remaining = self.run_extract("cat dog cat", r"cat")

        self.assertEqual("cat\ncat", processed)
        self.assertEqual(" dog ", remaining)

    def test_regex_extract_with_single_group_returns_group_text(self):
        processed, remaining = self.run_extract("id=42 id=99", r"id=(\d+)")

        self.assertEqual("42\n99", processed)
        self.assertEqual(" ", remaining)

    def test_regex_extract_with_multiple_groups_returns_deterministic_joined_text(self):
        processed, remaining = self.run_extract("color=blue size=large", r"(\w+)=(\w+)")

        self.assertEqual("color | blue\nsize | large", processed)
        self.assertEqual(" ", remaining)

    def test_regex_extract_supports_dotall_multiline_groups(self):
        text = "BEGIN\nalpha\nbeta\nEND"
        processed, remaining = self.run_extract(text, r"BEGIN\n(.*?)\nEND")

        self.assertEqual("alpha\nbeta", processed)
        self.assertEqual("", remaining)


if __name__ == "__main__":
    unittest.main()

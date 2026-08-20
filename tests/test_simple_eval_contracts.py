from __future__ import annotations

import builtins
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest import mock

import simpleeval

import simple_eval as subject


class SimpleEvalBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ints = subject.EvaluateInts()
        self.floats = subject.EvaluateFloats()
        self.strings = subject.EvaluateStrs()

    def assert_silent_result(self, call, expected) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            actual = call()
        self.assertEqual(expected, actual)
        self.assertEqual("", output.getvalue())

    def test_published_numeric_examples_and_precedence_are_stable(self) -> None:
        self.assert_silent_result(
            lambda: self.ints.evaluate("(a + b) * 2", "False", 3, 4, 0),
            (14, 14.0, "14"),
        )
        self.assert_silent_result(
            lambda: self.floats.evaluate("((a + b) - c) / 2", "False", 1.5, 3.5, 1.0),
            (2, 2.0, "2.0"),
        )
        self.assert_silent_result(
            lambda: self.ints.evaluate("a + b * c", "False", 2, 3, 4),
            (14, 14.0, "14"),
        )

    def test_string_examples_unicode_and_explicit_functions_are_stable(self) -> None:
        self.assert_silent_result(
            lambda: self.strings.evaluate("a + ' ' + b + c", "False", "Hello", "World", "!"),
            ("Hello World!",),
        )
        self.assert_silent_result(
            lambda: self.strings.evaluate("a + b", "False", "繁體", "中文"),
            ("繁體中文",),
        )
        self.assert_silent_result(
            lambda: self.strings.evaluate("str(len(a))", "False", "abcd", "", ""),
            ("4",),
        )

    def test_explicit_scalar_conversion_policy_is_stable(self) -> None:
        self.assert_silent_result(
            lambda: self.ints.evaluate("5 / 2", "False"),
            (2, 2.5, "2.5"),
        )
        self.assert_silent_result(
            lambda: self.floats.evaluate("-a", "False", 2.25),
            (-2, -2.25, "-2.25"),
        )
        self.assert_silent_result(
            lambda: self.ints.evaluate("True", "False"),
            (1, 1.0, "True"),
        )
        self.assert_silent_result(
            lambda: self.floats.evaluate("int(a) + float('1.25')", "False", 2.9),
            (3, 3.25, "3.25"),
        )

    def test_allowed_comparison_and_boolean_operators_are_deterministic(self) -> None:
        self.assert_silent_result(
            lambda: self.ints.evaluate("a < b and not False", "False", 1, 2, 0),
            (1, 1.0, "True"),
        )
        self.assert_silent_result(
            lambda: self.strings.evaluate("a == b or False", "False", "x", "x", ""),
            ("True",),
        )

    def test_random_and_mutated_upstream_default_functions_are_rejected(self) -> None:
        with mock.patch.dict(
            simpleeval.DEFAULT_FUNCTIONS,
            {"unexpected": lambda: 41},
            clear=False,
        ):
            for expression in ("rand()", "randint(1, 2)", "unexpected()"):
                with self.subTest(expression=expression):
                    self.assert_silent_result(
                        lambda expression=expression: self.ints.evaluate(expression, "False"),
                        (0, 0.0, "Error"),
                    )
            self.assert_silent_result(
                lambda: self.strings.evaluate("unexpected()", "False"),
                ("Error",),
            )

    def test_forbidden_access_syntax_and_operator_families_fail_closed(self) -> None:
        expressions = (
            "a.real",
            "a[0]",
            "1 << 2",
            "1 | 2",
            "'x' in a",
            "a is b",
            "[x for x in a]",
            "{'x': 1}",
            "(lambda: 1)()",
            "a if True else b",
            "f'{a}'",
            "__import__('os')",
        )
        for expression in expressions:
            with self.subTest(expression=expression):
                self.assert_silent_result(
                    lambda expression=expression: self.strings.evaluate(
                        expression, "False", "xy", "xy", ""
                    ),
                    ("Error",),
                )
        self.assert_silent_result(
            lambda: self.ints.evaluate("a.real", "False", 7),
            (0, 0.0, "Error"),
        )

    def test_syntax_runtime_nonfinite_complex_and_nonscalar_failures_are_stable(self) -> None:
        numeric_expressions = (
            "PRIVATE_CANARY +",
            "1 / 0",
            "float('nan')",
            "float('inf')",
            "1e309",
            "(-1) ** 0.5",
            "None",
        )
        for expression in numeric_expressions:
            with self.subTest(expression=expression):
                self.assert_silent_result(
                    lambda expression=expression: self.ints.evaluate(expression, "False"),
                    (0, 0.0, "Error"),
                )

    def test_expression_ast_power_and_string_limits_have_exact_boundaries(self) -> None:
        self.assertNotEqual(
            "Error",
            self.ints.evaluate("2 ** 1000", "False")[2],
        )
        for expression in ("2 ** 1001", "1001 ** 2"):
            with self.subTest(expression=expression):
                self.assert_silent_result(
                    lambda expression=expression: self.ints.evaluate(expression, "False"),
                    (0, 0.0, "Error"),
                )

        self.assert_silent_result(
            lambda: self.strings.evaluate("a", "False", "x" * 100_000),
            ("x" * 100_000,),
        )
        self.assert_silent_result(
            lambda: self.strings.evaluate("a", "False", "x" * 100_001),
            ("Error",),
        )
        self.assert_silent_result(
            lambda: self.strings.evaluate("len(a)", "False", "x" * 100_001),
            ("Error",),
        )
        self.assert_silent_result(
            lambda: self.strings.evaluate("a + b", "False", "x" * 50_000, "y" * 50_001),
            ("Error",),
        )
        self.assert_silent_result(
            lambda: self.ints.evaluate("1" + " " * 4_096, "False"),
            (0, 0.0, "Error"),
        )
        many_nodes = "+".join("1" for _ in range(130))
        self.assert_silent_result(
            lambda: self.ints.evaluate(many_nodes, "False"),
            (0, 0.0, "Error"),
        )

    def test_non_opt_in_errors_do_not_disclose_expression_value_or_exception(self) -> None:
        canaries = ("PRIVATE_EXPRESSION_CANARY", "PRIVATE_VALUE_CANARY")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.strings.evaluate(
                canaries[0] + " + missing_name",
                "False",
                canaries[1],
                "",
                "",
            )
        self.assertEqual(("Error",), result)
        self.assertEqual("", output.getvalue())

    def test_opt_in_success_is_bounded_and_failure_is_content_free(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.strings.evaluate("a", "True", "x" * 2_000)
        self.assertEqual(("x" * 2_000,), result)
        rendered = output.getvalue()
        self.assertIn("[Evaluate Strings]", rendered)
        self.assertIn("<truncated>", rendered)
        self.assertLess(len(rendered), 2_000)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.ints.evaluate("PRIVATE_FAILURE_CANARY +", "True")
        self.assertEqual((0, 0.0, "Error"), result)
        self.assertIn("[Evaluate Integers Error]", output.getvalue())
        self.assertNotIn("PRIVATE_FAILURE_CANARY", output.getvalue())


class SimpleEvalDependencyAbsenceTests(unittest.TestCase):
    def test_import_and_all_nodes_fail_consistently_without_dependency(self) -> None:
        module_path = Path(subject.__file__)
        module_name = "simple_eval_without_dependency_for_test"
        original_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name == "simpleeval" or name.startswith("simpleeval."):
                raise ImportError("PRIVATE_DEPENDENCY_CANARY")
            return original_import(name, *args, **kwargs)

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        output = io.StringIO()
        with mock.patch.object(builtins, "__import__", side_effect=blocked_import):
            with contextlib.redirect_stdout(output):
                spec.loader.exec_module(module)
                ints = module.EvaluateInts().evaluate("1 + 1", "False")
                floats = module.EvaluateFloats().evaluate("1 + 1", "False")
                strings = module.EvaluateStrs().evaluate("'a' + 'b'", "False")
        self.assertEqual((0, 0.0, "Error"), ints)
        self.assertEqual((0, 0.0, "Error"), floats)
        self.assertEqual(("Error",), strings)
        self.assertEqual("", output.getvalue())


class SimpleEvalPublicContractTests(unittest.TestCase):
    def test_policy_is_repository_owned_and_upstream_defaults_are_not_referenced(self) -> None:
        source = Path(subject.__file__).read_text(encoding="utf-8")
        self.assertNotIn("DEFAULT_FUNCTIONS", source)
        self.assertNotIn("DEFAULT_OPERATORS", source)
        self.assertNotIn("DEFAULT_NAMES", source)
        self.assertEqual(4_096, subject.MAX_EXPRESSION_LENGTH)
        self.assertEqual(256, subject.MAX_AST_NODES)
        self.assertEqual(100_000, subject.MAX_STRING_LENGTH)
        self.assertEqual(1_000, subject.MAX_POWER_ABS_OPERAND)

    def test_stable_node_and_schema_contracts_remain_exact(self) -> None:
        self.assertEqual(
            {"EvaluateInts", "EvaluateFloats", "EvaluateStrs"},
            set(subject.NODE_CLASS_MAPPINGS),
        )
        self.assertEqual(
            {
                "EvaluateInts": "Simple Eval (Integers)",
                "EvaluateFloats": "Simple Eval (Floats)",
                "EvaluateStrs": "Simple Eval (Strings)",
            },
            subject.NODE_DISPLAY_NAME_MAPPINGS,
        )

        cases = (
            (subject.EvaluateInts, ("INT", "FLOAT", "STRING"), "((a + b) - c) / 2"),
            (subject.EvaluateFloats, ("INT", "FLOAT", "STRING"), "((a + b) - c) / 2"),
            (subject.EvaluateStrs, ("STRING",), "a + ' ' + b + c"),
        )
        for node_class, return_types, default_expression in cases:
            with self.subTest(node=node_class.__name__):
                schema = node_class.INPUT_TYPES()
                self.assertEqual(
                    ["python_expression", "print_to_console"],
                    list(schema["required"]),
                )
                self.assertEqual(["a", "b", "c"], list(schema["optional"]))
                self.assertEqual(default_expression, schema["required"]["python_expression"][1]["default"])
                self.assertEqual(return_types, node_class.RETURN_TYPES)
                self.assertEqual("evaluate", node_class.FUNCTION)
                self.assertEqual("ComfyUI Text Processor/Logic", node_class.CATEGORY)


if __name__ == "__main__":
    unittest.main()

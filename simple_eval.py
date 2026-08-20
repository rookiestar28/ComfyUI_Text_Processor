from __future__ import annotations

import ast
import math
import operator
import sys
import tokenize
from io import StringIO
from types import MappingProxyType
from typing import Any, Callable, Mapping


MAX_EXPRESSION_LENGTH = 4_096
MAX_AST_NODES = 256
MAX_STRING_LENGTH = 100_000
MAX_POWER_ABS_OPERAND = 1_000
MAX_LOG_FIELD_LENGTH = 512


class ExpressionPolicyError(ValueError):
    """Raised when an expression is outside the repository-owned policy."""


def _guard_string_length(value: Any) -> None:
    if isinstance(value, str) and len(value) > MAX_STRING_LENGTH:
        raise ExpressionPolicyError("string limit exceeded")


def _safe_add(left: Any, right: Any) -> Any:
    if isinstance(left, str) and isinstance(right, str):
        if len(left) + len(right) > MAX_STRING_LENGTH:
            raise ExpressionPolicyError("string limit exceeded")
    return operator.add(left, right)


def _safe_multiply(left: Any, right: Any) -> Any:
    if isinstance(left, str) and isinstance(right, int):
        if len(left) * max(0, right) > MAX_STRING_LENGTH:
            raise ExpressionPolicyError("string limit exceeded")
    elif isinstance(right, str) and isinstance(left, int):
        if len(right) * max(0, left) > MAX_STRING_LENGTH:
            raise ExpressionPolicyError("string limit exceeded")
    return operator.mul(left, right)


def _safe_power(left: Any, right: Any) -> Any:
    try:
        outside_limit = (
            abs(left) > MAX_POWER_ABS_OPERAND
            or abs(right) > MAX_POWER_ABS_OPERAND
        )
    except TypeError as exc:
        raise ExpressionPolicyError("power operands must be numeric") from exc
    if outside_limit:
        raise ExpressionPolicyError("power operand limit exceeded")
    return operator.pow(left, right)


# SECURITY: upstream defaults include nondeterministic and broader operators; keep this explicit.
_OPERATORS: Mapping[type[ast.AST], Callable[..., Any]] = MappingProxyType(
    {
        ast.Add: _safe_add,
        ast.Sub: operator.sub,
        ast.Mult: _safe_multiply,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: _safe_power,
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
        ast.Not: operator.not_,
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }
)

_NUMERIC_FUNCTIONS: Mapping[str, Callable[..., Any]] = MappingProxyType(
    {"int": int, "float": float, "str": str}
)
_STRING_FUNCTIONS: Mapping[str, Callable[..., Any]] = MappingProxyType(
    {"len": len, "str": str}
)
_CONSTANT_NAMES: Mapping[str, Any] = MappingProxyType(
    {"True": True, "False": False, "None": None}
)

_ALLOWED_NODE_TYPES = frozenset(
    {
        ast.Module,
        ast.Expr,
        ast.Constant,
        ast.Name,
        ast.Load,
        ast.BinOp,
        ast.UnaryOp,
        ast.BoolOp,
        ast.Compare,
        ast.Call,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.UAdd,
        ast.USub,
        ast.Not,
        ast.And,
        ast.Or,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
    }
)


def _validate_expression(
    expression: str,
    variable_names: Mapping[str, Any],
    functions: Mapping[str, Callable[..., Any]],
) -> ast.expr:
    if not isinstance(expression, str):
        raise ExpressionPolicyError("expression must be text")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ExpressionPolicyError("expression limit exceeded")

    normalized_expression = expression.strip()
    for token in tokenize.generate_tokens(StringIO(normalized_expression).readline):
        if token.type == tokenize.OP and token.string == ";":
            raise ExpressionPolicyError("statement separator is not allowed")
    tree = ast.parse(normalized_expression)
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise ExpressionPolicyError("expression complexity limit exceeded")

    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        raise ExpressionPolicyError("exactly one expression is required")

    allowed_names = set(variable_names) | set(_CONSTANT_NAMES) | set(functions)
    for node in nodes:
        if type(node) not in _ALLOWED_NODE_TYPES:
            raise ExpressionPolicyError(f"unsupported syntax: {type(node).__name__}")

        if isinstance(node, ast.Constant):
            if type(node.value) not in {bool, int, float, str, type(None)}:
                raise ExpressionPolicyError("unsupported literal")
            _guard_string_length(node.value)
            if isinstance(node.value, float) and not math.isfinite(node.value):
                raise ExpressionPolicyError("non-finite literal")
        elif isinstance(node, ast.Name):
            if node.id not in allowed_names or node.id.startswith("_"):
                raise ExpressionPolicyError("name is not allowed")
        elif isinstance(node, ast.Call):
            if (
                not isinstance(node.func, ast.Name)
                or node.func.id not in functions
                or node.keywords
            ):
                raise ExpressionPolicyError("function call is not allowed")
        elif isinstance(node, ast.BinOp) and type(node.op) not in _OPERATORS:
            raise ExpressionPolicyError("binary operator is not allowed")
        elif isinstance(node, ast.UnaryOp) and type(node.op) not in _OPERATORS:
            raise ExpressionPolicyError("unary operator is not allowed")
        elif isinstance(node, ast.BoolOp) and type(node.op) not in {ast.And, ast.Or}:
            raise ExpressionPolicyError("boolean operator is not allowed")
        elif isinstance(node, ast.Compare):
            if any(type(comparator) not in _OPERATORS for comparator in node.ops):
                raise ExpressionPolicyError("comparison operator is not allowed")
    return tree.body[0].value


def _validate_variable_types(
    variables: Mapping[str, Any],
    allowed_types: tuple[type, ...],
) -> None:
    # SECURITY: reject custom objects before any overloaded evaluator operation can run.
    if any(type(value) not in allowed_types for value in variables.values()):
        raise ExpressionPolicyError("variable type is not allowed")


def _guard_intermediate(value: Any) -> Any:
    if type(value) not in {bool, int, float, str, type(None), complex}:
        raise ExpressionPolicyError("non-scalar result")
    _guard_string_length(value)
    return value


def _interpret_node(
    node: ast.expr,
    names: Mapping[str, Any],
    functions: Mapping[str, Callable[..., Any]],
) -> Any:
    # SECURITY: keep dispatch exhaustive; generic AST execution would bypass the allowlist.
    if isinstance(node, ast.Constant):
        return _guard_intermediate(node.value)
    if isinstance(node, ast.Name):
        if node.id in names:
            return _guard_intermediate(names[node.id])
        raise ExpressionPolicyError("name is not allowed")
    if isinstance(node, ast.BinOp):
        operation = _OPERATORS.get(type(node.op))
        if operation is None:
            raise ExpressionPolicyError("binary operator is not allowed")
        return _guard_intermediate(
            operation(
                _interpret_node(node.left, names, functions),
                _interpret_node(node.right, names, functions),
            )
        )
    if isinstance(node, ast.UnaryOp):
        operation = _OPERATORS.get(type(node.op))
        if operation is None:
            raise ExpressionPolicyError("unary operator is not allowed")
        return _guard_intermediate(
            operation(_interpret_node(node.operand, names, functions))
        )
    if isinstance(node, ast.BoolOp):
        values = iter(node.values)
        result = _interpret_node(next(values), names, functions)
        if isinstance(node.op, ast.And):
            for value in values:
                if not result:
                    return _guard_intermediate(result)
                result = _interpret_node(value, names, functions)
            return _guard_intermediate(result)
        if isinstance(node.op, ast.Or):
            for value in values:
                if result:
                    return _guard_intermediate(result)
                result = _interpret_node(value, names, functions)
            return _guard_intermediate(result)
        raise ExpressionPolicyError("boolean operator is not allowed")
    if isinstance(node, ast.Compare):
        left = _interpret_node(node.left, names, functions)
        for operator_node, comparator_node in zip(
            node.ops,
            node.comparators,
            strict=True,
        ):
            operation = _OPERATORS.get(type(operator_node))
            if operation is None:
                raise ExpressionPolicyError("comparison operator is not allowed")
            right = _interpret_node(comparator_node, names, functions)
            if not operation(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        # SECURITY: only direct bare-name calls resolved from the immutable owned map.
        if not isinstance(node.func, ast.Name) or node.func.id not in functions:
            raise ExpressionPolicyError("function call is not allowed")
        arguments = [
            _interpret_node(argument, names, functions) for argument in node.args
        ]
        return _guard_intermediate(functions[node.func.id](*arguments))
    raise ExpressionPolicyError(f"unsupported syntax: {type(node).__name__}")


def _evaluate_expression(
    expression: str,
    variables: Mapping[str, Any],
    functions: Mapping[str, Callable[..., Any]],
) -> Any:
    for value in variables.values():
        _guard_string_length(value)
    expression_node = _validate_expression(expression, variables, functions)
    names = dict(_CONSTANT_NAMES)
    names.update(variables)
    return _interpret_node(expression_node, names, functions)


def _convert_numeric_result(result: Any) -> tuple[int, float, str]:
    if isinstance(result, complex):
        raise ExpressionPolicyError("complex result")
    if isinstance(result, float) and not math.isfinite(result):
        raise ExpressionPolicyError("non-finite result")

    int_result = int(result)
    float_result = float(result)
    if not math.isfinite(float_result):
        raise ExpressionPolicyError("non-finite result")
    string_result = str(result)
    _guard_string_length(string_result)
    return int_result, float_result, string_result


def _convert_string_result(result: Any) -> tuple[str]:
    if isinstance(result, complex):
        raise ExpressionPolicyError("complex result")
    if isinstance(result, float) and not math.isfinite(result):
        raise ExpressionPolicyError("non-finite result")
    string_result = str(result)
    _guard_string_length(string_result)
    return (string_result,)


def _bounded_repr(value: Any) -> str:
    try:
        rendered = repr(value)
    except Exception:
        rendered = f"<{type(value).__name__}>"
    rendered = rendered.replace("\r", "\\r").replace("\n", "\\n")
    marker = "...<truncated>"
    if len(rendered) > MAX_LOG_FIELD_LENGTH:
        rendered = rendered[: MAX_LOG_FIELD_LENGTH - len(marker)] + marker
    return rendered


def _print_success(
    node_name: str,
    variables: Mapping[str, Any],
    expression: str,
    result: Any,
) -> None:
    print(f"\n[{node_name}]")
    print(f"Vars: {_bounded_repr(dict(variables))}")
    print(f"Expr: {_bounded_repr(expression)}")
    print(f"Result: {_bounded_repr(result)}")


def _print_failure(node_name: str, error: Exception) -> None:
    # PRIVACY: never print expressions, values, or third-party error payloads here.
    print(f"\n[{node_name} Error]")
    print(f"Evaluation failed ({type(error).__name__}).")


class _EvaluateMixin:
    _node_name: str
    _functions: Mapping[str, Callable[..., Any]]
    _fallback: tuple[Any, ...]
    _variable_types: tuple[type, ...]

    def _run(
        self,
        expression: str,
        print_to_console: str,
        variables: Mapping[str, Any],
        converter: Callable[[Any], tuple[Any, ...]],
    ) -> tuple[Any, ...]:
        try:
            _validate_variable_types(variables, self._variable_types)
            result = _evaluate_expression(expression, variables, self._functions)
            converted = converter(result)
            if print_to_console == "True":
                _print_success(self._node_name, variables, expression, result)
            return converted
        except Exception as error:
            if print_to_console == "True":
                _print_failure(self._node_name, error)
            return self._fallback


class EvaluateInts(_EvaluateMixin):
    _node_name = "Evaluate Integers"
    _functions = _NUMERIC_FUNCTIONS
    _fallback = (0, 0.0, "Error")
    _variable_types = (int,)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "python_expression": (
                    "STRING",
                    {
                        "default": "((a + b) - c) / 2",
                        "multiline": False,
                        "tooltip": "Numeric expression evaluated with integer variables a, b, and c.",
                    },
                ),
                "print_to_console": (
                    ["False", "True"],
                    {"tooltip": "Print variables, expression, and result to the server console."},
                ),
            },
            "optional": {
                "a": (
                    "INT",
                    {
                        "default": 0,
                        "min": -sys.maxsize,
                        "max": sys.maxsize,
                        "step": 1,
                        "tooltip": "Integer value bound to variable a.",
                    },
                ),
                "b": (
                    "INT",
                    {
                        "default": 0,
                        "min": -sys.maxsize,
                        "max": sys.maxsize,
                        "step": 1,
                        "tooltip": "Integer value bound to variable b.",
                    },
                ),
                "c": (
                    "INT",
                    {
                        "default": 0,
                        "min": -sys.maxsize,
                        "max": sys.maxsize,
                        "step": 1,
                        "tooltip": "Integer value bound to variable c.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("INT", "FLOAT", "STRING")
    OUTPUT_NODE = True
    FUNCTION = "evaluate"
    CATEGORY = "ComfyUI Text Processor/Logic"
    DESCRIPTION = "Evaluates a numeric expression with integer inputs and returns int, float, and string forms."
    SEARCH_ALIASES = [
        "simple expression int",
        "integer expression",
        "math expression",
        "logic integer",
    ]
    OUTPUT_TOOLTIPS = ("Integer result.", "Float result.", "String representation of the result.")

    def evaluate(self, python_expression, print_to_console, a=0, b=0, c=0):
        return self._run(
            python_expression,
            print_to_console,
            {"a": a, "b": b, "c": c},
            _convert_numeric_result,
        )


class EvaluateFloats(_EvaluateMixin):
    _node_name = "Evaluate Floats"
    _functions = _NUMERIC_FUNCTIONS
    _fallback = (0, 0.0, "Error")
    _variable_types = (int, float)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "python_expression": (
                    "STRING",
                    {
                        "default": "((a + b) - c) / 2",
                        "multiline": False,
                        "tooltip": "Numeric expression evaluated with floating-point variables a, b, and c.",
                    },
                ),
                "print_to_console": (
                    ["False", "True"],
                    {"tooltip": "Print variables, expression, and result to the server console."},
                ),
            },
            "optional": {
                "a": (
                    "FLOAT",
                    {
                        "default": 0,
                        "min": -sys.float_info.max,
                        "max": sys.float_info.max,
                        "step": 0.01,
                        "tooltip": "Floating-point value bound to variable a.",
                    },
                ),
                "b": (
                    "FLOAT",
                    {
                        "default": 0,
                        "min": -sys.float_info.max,
                        "max": sys.float_info.max,
                        "step": 0.01,
                        "tooltip": "Floating-point value bound to variable b.",
                    },
                ),
                "c": (
                    "FLOAT",
                    {
                        "default": 0,
                        "min": -sys.float_info.max,
                        "max": sys.float_info.max,
                        "step": 0.01,
                        "tooltip": "Floating-point value bound to variable c.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("INT", "FLOAT", "STRING")
    OUTPUT_NODE = True
    FUNCTION = "evaluate"
    CATEGORY = "ComfyUI Text Processor/Logic"
    DESCRIPTION = "Evaluates a numeric expression with float inputs and returns int, float, and string forms."
    SEARCH_ALIASES = [
        "simple expression float",
        "float expression",
        "math expression",
        "logic float",
    ]
    OUTPUT_TOOLTIPS = ("Integer-cast result.", "Float result.", "String representation of the result.")

    def evaluate(self, python_expression, print_to_console, a=0.0, b=0.0, c=0.0):
        return self._run(
            python_expression,
            print_to_console,
            {"a": a, "b": b, "c": c},
            _convert_numeric_result,
        )


class EvaluateStrs(_EvaluateMixin):
    _node_name = "Evaluate Strings"
    _functions = _STRING_FUNCTIONS
    _fallback = ("Error",)
    _variable_types = (str,)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "python_expression": (
                    "STRING",
                    {
                        "default": "a + ' ' + b + c",
                        "multiline": False,
                        "tooltip": "String expression evaluated with text variables a, b, and c.",
                    },
                ),
                "print_to_console": (
                    ["False", "True"],
                    {"tooltip": "Print variables, expression, and result to the server console."},
                ),
            },
            "optional": {
                "a": (
                    "STRING",
                    {
                        "default": "Hello",
                        "multiline": False,
                        "tooltip": "Text value bound to variable a.",
                    },
                ),
                "b": (
                    "STRING",
                    {
                        "default": "World",
                        "multiline": False,
                        "tooltip": "Text value bound to variable b.",
                    },
                ),
                "c": (
                    "STRING",
                    {
                        "default": "!",
                        "multiline": False,
                        "tooltip": "Text value bound to variable c.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "evaluate"
    CATEGORY = "ComfyUI Text Processor/Logic"
    DESCRIPTION = "Evaluates a string expression with three string variables."
    SEARCH_ALIASES = [
        "simple expression string",
        "string expression",
        "text expression",
        "logic string",
    ]
    OUTPUT_TOOLTIPS = ("String evaluation result.",)

    def evaluate(self, python_expression, print_to_console, a="", b="", c=""):
        return self._run(
            python_expression,
            print_to_console,
            {"a": a, "b": b, "c": c},
            _convert_string_result,
        )


NODE_CLASS_MAPPINGS = {
    "EvaluateInts": EvaluateInts,
    "EvaluateFloats": EvaluateFloats,
    "EvaluateStrs": EvaluateStrs,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "EvaluateInts": "Simple Expression (Integers)",
    "EvaluateFloats": "Simple Expression (Floats)",
    "EvaluateStrs": "Simple Expression (Strings)",
}

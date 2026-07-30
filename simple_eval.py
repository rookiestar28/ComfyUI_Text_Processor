import sys
import math

try:
    import simpleeval
    from simpleeval import simple_eval
except ImportError:
    print("\033[31m[ComfyUI Text Processor] Error: 'simpleeval' module not found.\033[0m")
    print("Please run: pip install simpleeval")
    def simple_eval(*args, **kwargs):
        raise ImportError("simpleeval library is required. Please install it.")

class EvaluateInts:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "python_expression": ("STRING", {
                    "default": "((a + b) - c) / 2",
                    "multiline": False,
                    "tooltip": "Numeric expression evaluated with integer variables a, b, and c.",
                }),
                "print_to_console": (
                    ["False", "True"],
                    {"tooltip": "Print variables, expression, and result to the server console."},
                ),
            },
            "optional": {
                "a": ("INT", {
                    "default": 0,
                    "min": -sys.maxsize,
                    "max": sys.maxsize,
                    "step": 1,
                    "tooltip": "Integer value bound to variable a.",
                }),
                "b": ("INT", {
                    "default": 0,
                    "min": -sys.maxsize,
                    "max": sys.maxsize,
                    "step": 1,
                    "tooltip": "Integer value bound to variable b.",
                }),
                "c": ("INT", {
                    "default": 0,
                    "min": -sys.maxsize,
                    "max": sys.maxsize,
                    "step": 1,
                    "tooltip": "Integer value bound to variable c.",
                }),
            },
        }

    RETURN_TYPES = ("INT", "FLOAT", "STRING",)
    OUTPUT_NODE = True
    FUNCTION = "evaluate"
    CATEGORY = "ComfyUI Text Processor/Logic"
    DESCRIPTION = "Evaluates a numeric expression with integer inputs and returns int, float, and string forms."
    SEARCH_ALIASES = ["simple eval int", "integer expression", "math eval", "logic integer"]
    OUTPUT_TOOLTIPS = ("Integer result.", "Float result.", "String representation of the result.")

    def evaluate(self, python_expression, print_to_console, a=0, b=0, c=0):
        names = {'a': a, 'b': b, 'c': c}
        try:
            result = simple_eval(python_expression, names=names)
            int_result = int(result)
            float_result = float(result)
            string_result = str(result)
            if print_to_console == "True":
                self._print_log("Evaluate Integers", names, python_expression, result)
            return (int_result, float_result, string_result,)
        except Exception as e:
            print(f"\033[31m[Eval Int Error] Expression: {python_expression}\nError: {e}\033[0m")
            return (0, 0.0, "Error")

    def _print_log(self, node_name, vars, expr, result):
        print(f"\n[{node_name}]")
        print(f"Vars: {vars}")
        print(f"Expr: {expr}")
        print(f"Result: {result}")


class EvaluateFloats:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "python_expression": ("STRING", {
                    "default": "((a + b) - c) / 2",
                    "multiline": False,
                    "tooltip": "Numeric expression evaluated with floating-point variables a, b, and c.",
                }),
                "print_to_console": (
                    ["False", "True"],
                    {"tooltip": "Print variables, expression, and result to the server console."},
                ),
            },
            "optional": {
                "a": ("FLOAT", {
                    "default": 0,
                    "min": -sys.float_info.max,
                    "max": sys.float_info.max,
                    "step": 0.01,
                    "tooltip": "Floating-point value bound to variable a.",
                }),
                "b": ("FLOAT", {
                    "default": 0,
                    "min": -sys.float_info.max,
                    "max": sys.float_info.max,
                    "step": 0.01,
                    "tooltip": "Floating-point value bound to variable b.",
                }),
                "c": ("FLOAT", {
                    "default": 0,
                    "min": -sys.float_info.max,
                    "max": sys.float_info.max,
                    "step": 0.01,
                    "tooltip": "Floating-point value bound to variable c.",
                }),
            },
        }

    RETURN_TYPES = ("INT", "FLOAT", "STRING",)
    OUTPUT_NODE = True
    FUNCTION = "evaluate"
    CATEGORY = "ComfyUI Text Processor/Logic"
    DESCRIPTION = "Evaluates a numeric expression with float inputs and returns int, float, and string forms."
    SEARCH_ALIASES = ["simple eval float", "float expression", "math eval", "logic float"]
    OUTPUT_TOOLTIPS = ("Integer-cast result.", "Float result.", "String representation of the result.")

    def evaluate(self, python_expression, print_to_console, a=0.0, b=0.0, c=0.0):
        names = {'a': a, 'b': b, 'c': c}
        try:
            result = simple_eval(python_expression, names=names)
            int_result = int(result)
            float_result = float(result)
            string_result = str(result)
            if print_to_console == "True":
                self._print_log("Evaluate Floats", names, python_expression, result)
            return (int_result, float_result, string_result,)
        except Exception as e:
            print(f"\033[31m[Eval Float Error] Expression: {python_expression}\nError: {e}\033[0m")
            return (0, 0.0, "Error")

    def _print_log(self, node_name, vars, expr, result):
        print(f"\n[{node_name}]")
        print(f"Vars: {vars}")
        print(f"Expr: {expr}")
        print(f"Result: {result}")


class EvaluateStrs:
    """
    Evaluate Strings: 使用 Python 表達式處理字符串。
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "python_expression": ("STRING", {
                    "default": "a + ' ' + b + c",
                    "multiline": False,
                    "tooltip": "String expression evaluated with text variables a, b, and c.",
                }),
                "print_to_console": (
                    ["False", "True"],
                    {"tooltip": "Print variables, expression, and result to the server console."},
                ),
            },
            "optional": {
                "a": ("STRING", {
                    "default": "Hello",
                    "multiline": False,
                    "tooltip": "Text value bound to variable a.",
                }),
                "b": ("STRING", {
                    "default": "World",
                    "multiline": False,
                    "tooltip": "Text value bound to variable b.",
                }),
                "c": ("STRING", {
                    "default": "!",
                    "multiline": False,
                    "tooltip": "Text value bound to variable c.",
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "evaluate"
    CATEGORY = "ComfyUI Text Processor/Logic"
    DESCRIPTION = "Evaluates a string expression with three string variables."
    SEARCH_ALIASES = ["simple eval string", "string expression", "text expression", "logic string"]
    OUTPUT_TOOLTIPS = ("String evaluation result.",)

    def evaluate(self, python_expression, print_to_console, a="", b="", c=""):
        names = {'a': a, 'b': b, 'c': c}
        functions = simpleeval.DEFAULT_FUNCTIONS.copy()
        functions.update({"len": len, "str": str})

        try:
            result = simple_eval(python_expression, names=names, functions=functions)
            string_result = str(result)
            if print_to_console == "True":
                self._print_log("Evaluate Strings", names, python_expression, result)
            return (string_result,)
        except Exception as e:
            print(f"\033[31m[Eval Str Error] Expression: {python_expression}\nError: {e}\033[0m")
            return ("Error",)

    def _print_log(self, node_name, vars, expr, result):
        print(f"\n[{node_name}]")
        print(f"Vars: {vars}")
        print(f"Expr: {expr}")
        print(f"Result: {result}")


NODE_CLASS_MAPPINGS = {
    "EvaluateInts": EvaluateInts,
    "EvaluateFloats": EvaluateFloats,
    "EvaluateStrs": EvaluateStrs
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "EvaluateInts": "Simple Eval (Integers)",
    "EvaluateFloats": "Simple Eval (Floats)",
    "EvaluateStrs": "Simple Eval (Strings)"
}

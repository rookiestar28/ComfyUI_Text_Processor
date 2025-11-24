import sys
import math

try:
    import simpleeval
    from simpleeval import simple_eval
except ImportError:
    print("\033[31m[ComfyUI_Text_Processor] Error: 'simpleeval' module not found.\033[0m")
    print("Please run: pip install simpleeval")
    def simple_eval(*args, **kwargs):
        raise ImportError("simpleeval library is required. Please install it.")

class EvaluateInts:
    """
    Evaluate Integers: 使用 Python 表達式計算整數。
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "python_expression": ("STRING", {"default": "((a + b) - c) / 2", "multiline": False}),
                "print_to_console": (["False", "True"],), 
            },
            "optional": {
                "a": ("INT", {"default": 0, "min": -sys.maxsize, "max": sys.maxsize, "step": 1}),
                "b": ("INT", {"default": 0, "min": -sys.maxsize, "max": sys.maxsize, "step": 1}),
                "c": ("INT", {"default": 0, "min": -sys.maxsize, "max": sys.maxsize, "step": 1}), 
            },
        }

    RETURN_TYPES = ("INT", "FLOAT", "STRING",)
    OUTPUT_NODE = True
    FUNCTION = "evaluate"
    CATEGORY = "ComfyUI Text Processor/Logic"

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
    """
    Evaluate Floats: 使用 Python 表達式計算浮點數。
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "python_expression": ("STRING", {"default": "((a + b) - c) / 2", "multiline": False}),
                "print_to_console": (["False", "True"],), 
            },
            "optional": {
                "a": ("FLOAT", {"default": 0, "min": -sys.float_info.max, "max": sys.float_info.max, "step": 0.01}),
                "b": ("FLOAT", {"default": 0, "min": -sys.float_info.max, "max": sys.float_info.max, "step": 0.01}),
                "c": ("FLOAT", {"default": 0, "min": -sys.float_info.max, "max": sys.float_info.max, "step": 0.01}), 
            },
        }

    RETURN_TYPES = ("INT", "FLOAT", "STRING",)
    OUTPUT_NODE = True
    FUNCTION = "evaluate"
    CATEGORY = "ComfyUI_Text_Processor/Logic"

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
                "python_expression": ("STRING", {"default": "a + ' ' + b + c", "multiline": False}),
                "print_to_console": (["False", "True"],),
            },
            "optional": {
                "a": ("STRING", {"default": "Hello", "multiline": False}),
                "b": ("STRING", {"default": "World", "multiline": False}),
                "c": ("STRING", {"default": "!", "multiline": False}), 
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "evaluate"
    CATEGORY = "ComfyUI_Text_Processor/Logic"

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
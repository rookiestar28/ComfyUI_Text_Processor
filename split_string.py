class SplitString:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Text to split at the first matching delimiter.",
                    },
                ),
                "delimiter": (
                    "STRING",
                    {
                        "default": "|",
                        "multiline": False,
                        "tooltip": "Literal non-empty delimiter used for the first split.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("left", "right")
    OUTPUT_TOOLTIPS = (
        "Text before the first delimiter, or the original text when no delimiter is found.",
        "Text after the first delimiter, or an empty string when no delimiter is found.",
    )
    FUNCTION = "split_string"
    CATEGORY = "ComfyUI Text Processor"
    DESCRIPTION = "Splits text once at the first literal delimiter into left and right outputs."
    SEARCH_ALIASES = ["split string", "split text", "string delimiter", "text delimiter"]

    def split_string(self, text, delimiter):
        if delimiter == "":
            raise ValueError("delimiter must not be empty")

        parts = text.split(delimiter, 1)
        if len(parts) == 1:
            return text, ""
        return parts[0], parts[1]


NODE_CLASS_MAPPINGS = {"TP_SplitString": SplitString}
NODE_DISPLAY_NAME_MAPPINGS = {"TP_SplitString": "Split String"}

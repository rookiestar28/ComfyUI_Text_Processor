import re
from typing import Tuple, Optional, Any

class AdvancedTextFilter:
    """
    這個節點根據指定的操作處理輸入文本，並提供兩個輸出：
    1. processed_text: 操作的主要結果。
    2. remaining_text: 被移除或未被選中的部分文本。
    """
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        operation_modes = [
            "find and remove (use optional_text)",
            "find and replace (use optional_text, replace_with_text)",
            "find all (extract) (use optional_text)",
            
            "extract between",
            "remove between",
            
            "extract before start text",
            "extract after start text",
            "remove before start text",
            "remove after start text",
            
            "remove empty lines",
            "remove newlines",
            "strip lines (trim)",
            "remove all whitespace (keep newlines)"
        ]
        
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": ""}),
                "concat_mode": (["disabled", "prepend_external_text", "append_external_text"],),
                "operation": (operation_modes,),
                
                "start_text": ("STRING", {"multiline": False, "default": ""}),
                "end_text": ("STRING", {"multiline": False, "default": ""}),
                
                "optional_text_input": ("STRING", {"multiline": False, "default": "", "placeholder": "用於 Find... 可用 , 分隔多個"}),
                "replace_with_text": ("STRING", {"multiline": False, "default": "", "placeholder": "用於 Find and Replace"}),
                
                "use_regex": ("BOOLEAN", {"default": False}),
                "case_conversion": (["disabled", "to UPPERCASE", "to lowercase"],),
            },
            "optional": {
                "external_text": ("*",), 
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("processed_text (Target)", "remaining_text")

    FUNCTION = "process"
    CATEGORY = "Text Processor"

    def process(self, text: str, concat_mode: str, operation: str, 
                start_text: str, end_text: str, 
                optional_text_input: str, replace_with_text: str, 
                use_regex: bool, case_conversion: str, 
                external_text: Optional[Any] = None) -> Tuple[str, str]:

        text_to_process = text
        if external_text is not None and concat_mode != "disabled":
            external_text_str = str(external_text)
            if concat_mode == "prepend_external_text":
                text_to_process = external_text_str + text_to_process
            elif concat_mode == "append_external_text":
                text_to_process = text_to_process + external_text_str
        
        if case_conversion == "to UPPERCASE":
            text_to_process = text_to_process.upper()
        elif case_conversion == "to lowercase":
            text_to_process = text_to_process.lower()

        original_text_input = text_to_process
        
        try:
            if operation == "remove empty lines":
                processed_lines = [line for line in text_to_process.splitlines() if line.strip()]
                return ("\n".join(processed_lines), "")

            elif operation == "remove newlines":
                processed = text_to_process.replace("\r", "").replace("\n", "")
                return (processed, "")

            elif operation == "strip lines (trim)":
                processed_lines = [line.strip() for line in text_to_process.splitlines()]
                return ("\n".join(processed_lines), "")

            elif operation == "remove all whitespace (keep newlines)":
                processed_lines = ["".join(line.split()) for line in text_to_process.splitlines()]
                return ("\n".join(processed_lines), "")

            elif operation.startswith("find"):
                if not optional_text_input:
                    if "extract" in operation:
                        return ("", original_text_input)
                    return (original_text_input, "")

                patterns = [p.strip() for p in optional_text_input.split(',') if p.strip()]
                
                if not patterns:
                     raise ValueError("optional_text_input is empty or contains only delimiters")

                all_found_matches = []

                if operation == "find all (extract) (use optional_text)":
                    remaining_output = text_to_process
                    
                    for pattern in patterns:
                        if use_regex:
                            found = re.findall(pattern, text_to_process)
                            all_found_matches.extend(found)
                            remaining_output = re.sub(pattern, "", remaining_output)
                        else:
                            count = text_to_process.count(pattern)
                            if count > 0:
                                all_found_matches.extend([pattern] * count)
                            remaining_output = remaining_output.replace(pattern, "")
                    
                    processed_output = "\n".join(all_found_matches)
                    return (processed_output, remaining_output)

                else:
                    temp_processed_text = text_to_process
                    replace_str = replace_with_text if "replace" in operation else ""

                    for pattern in patterns:
                        if use_regex:
                            found = re.findall(pattern, temp_processed_text)
                            all_found_matches.extend(found)
                            temp_processed_text = re.sub(pattern, replace_str, temp_processed_text)
                        else:
                            count = temp_processed_text.count(pattern)
                            if count > 0:
                                all_found_matches.extend([pattern] * count)
                            temp_processed_text = temp_processed_text.replace(pattern, replace_str)
                    
                    processed_output = temp_processed_text
                    remaining_output = "\n".join(all_found_matches)
                    return (processed_output, remaining_output)

            elif "start text" in operation:
                if not start_text:
                    raise ValueError("start_text is required for this operation")
                
                split_index = -1
                
                if use_regex:
                    match = re.search(start_text, text_to_process)
                    if not match:
                        raise ValueError(f"Start text regex '{start_text}' not found")
                    split_index = match.start()
                else:
                    split_index = text_to_process.find(start_text)
                    if split_index == -1:
                        raise ValueError(f"Start text '{start_text}' not found")

                part_before = text_to_process[:split_index]
                part_after = text_to_process[split_index:]
                
                if "extract before" in operation or "remove after" in operation:
                    return (part_before, part_after)
                else: # extract after / remove before
                    return (part_after, part_before)

            elif "between" in operation:
                if not start_text or not end_text:
                    return ("", text_to_process) if operation == "extract between" else (text_to_process, "")

                if use_regex:
                    start_match = re.search(start_text, text_to_process)
                    if not start_match:
                        raise ValueError(f"Start text regex '{start_text}' not found")
                    
                    start_of_target = start_match.end()

                    end_match = re.search(end_text, text_to_process[start_of_target:])
                    if not end_match:
                        raise ValueError(f"End text regex '{end_text}' not found after start text")

                    end_of_target = start_of_target + end_match.start()

                else:
                    start_index = text_to_process.find(start_text)
                    if start_index == -1:
                        raise ValueError(f"Start text '{start_text}' not found")
                    
                    start_of_target = start_index + len(start_text)
                    
                    end_of_target = text_to_process.find(end_text, start_of_target)
                    if end_of_target == -1:
                        raise ValueError(f"End text '{end_text}' not found after start text")

                target_text = text_to_process[start_of_target:end_of_target]
                before_text = text_to_process[:start_of_target]
                after_text = text_to_process[end_of_target:]

                if operation == "extract between":
                    return (target_text, before_text + after_text)
                else: # remove between
                    return (before_text + after_text, target_text)

        except ValueError as e:
            print(f"[AdvancedTextFilter] Value Warning: {e}")
            if operation.startswith("extract") or operation.startswith("find all"):
                return ("", original_text_input) 
            else:
                return (original_text_input, "") 
        
        except re.error as e:
            print(f"[AdvancedTextFilter] Regex Error: {e}")
            return (original_text_input, f"REGEX ERROR: {e}")

        except Exception as e:
            print(f"[AdvancedTextFilter] Generic Error: {e}")
            return (original_text_input, str(e)) 

        # Fallback for unknown operation
        return (text_to_process, "Unknown operation")
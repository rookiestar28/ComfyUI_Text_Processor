import re
from typing import Tuple, Optional, Any

class AdvancedTextFilter:
    """
    v1.1.5 Key Updates:
    1. New LLM Utilities: Added functions to extract code blocks, extract JSON objects, and clean Markdown formatting.
    2. Enhanced Boundary Handling: Added 'if_not_found' option to prevent workflow crashes when matches are missing.
    3. Optimized Regex: Added support for DOTALL mode (enabling multi-line matching).
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
            "remove all whitespace (keep newlines)",
            
            "LLM: extract code block (```)",
            "LLM: extract JSON object ({...})",
            "LLM: clean markdown formatting"
        ]
        
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": ""}),
                "concat_mode": (["disabled", "prepend_external_text", "append_external_text"],),
                "operation": (operation_modes,),
                
                "start_text": ("STRING", {"multiline": False, "default": ""}),
                "end_text": ("STRING", {"multiline": False, "default": ""}),
                
                "optional_text_input": ("STRING", {"multiline": False, "default": "", "placeholder": "Patterns separator: , (comma)"}),
                "replace_with_text": ("STRING", {"multiline": False, "default": "", "placeholder": "For Find and Replace"}),
                
                "use_regex": ("BOOLEAN", {"default": False}),
                "case_conversion": (["disabled", "to UPPERCASE", "to lowercase"],),
                
                "if_not_found": (["return original text", "return empty string", "trigger error"], {"default": "return original text"}),
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
                if_not_found: str,
                external_text: Optional[Any] = None) -> Tuple[str, str]:

        if text is None:
            text = ""
        text_to_process = str(text)

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
        
        def handle_not_found(original: str, reason: str):
            if if_not_found == "trigger error":
                raise ValueError(f"[AdvancedTextFilter] {reason}")
            elif if_not_found == "return empty string":
                if "extract" in operation or "find all" in operation or "LLM" in operation:
                    return ("", original)
                return (original, "") 
            else: # return original text
                if "extract" in operation or "find all" in operation or "LLM" in operation:
                    return ("", original) 
                return (original, "")

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
            
            elif operation == "LLM: extract code block (```)":
                pattern = r"```[\w]*\n?(.*?)```"
                matches = re.findall(pattern, text_to_process, re.DOTALL)
                if not matches:
                    return handle_not_found(text_to_process, "No code blocks found")
                
                extracted_code = "\n\n".join(matches)
                remaining = re.sub(pattern, "", text_to_process, flags=re.DOTALL)
                return (extracted_code.strip(), remaining.strip())

            elif operation == "LLM: extract JSON object ({...})":
                start_idx = text_to_process.find("{")
                end_idx = text_to_process.rfind("}")
                
                if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
                    return handle_not_found(text_to_process, "No valid JSON brackets found")
                
                json_content = text_to_process[start_idx:end_idx+1]
                remaining = text_to_process[:start_idx] + text_to_process[end_idx+1:]
                return (json_content, remaining)

            elif operation == "LLM: clean markdown formatting":
                cleaned = text_to_process
                cleaned = re.sub(r'\*\*|__|\*|_', '', cleaned)
                cleaned = re.sub(r'^#+\s+', '', cleaned, flags=re.MULTILINE)
                cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', cleaned)
                cleaned = re.sub(r'`', '', cleaned)
                return (cleaned, "")

            elif operation.startswith("find"):
                if not optional_text_input:
                    return handle_not_found(original_text_input, "optional_text_input is empty")

                patterns = [p.strip() for p in optional_text_input.split(',') if p.strip()]
                if not patterns:
                     return handle_not_found(original_text_input, "No valid patterns provided")

                all_found_matches = []
                
                if "extract" in operation:
                    remaining_output = text_to_process
                    for pattern in patterns:
                        if use_regex:
                            found = re.findall(pattern, text_to_process, re.DOTALL)
                            all_found_matches.extend(found)
                            remaining_output = re.sub(pattern, "", remaining_output, flags=re.DOTALL)
                        else:
                            count = text_to_process.count(pattern)
                            if count > 0:
                                all_found_matches.extend([pattern] * count)
                            remaining_output = remaining_output.replace(pattern, "")
                    
                    if not all_found_matches:
                        return handle_not_found(original_text_input, "Pattern not found")

                    processed_output = "\n".join(all_found_matches)
                    return (processed_output, remaining_output)

                else:
                    temp_processed_text = text_to_process
                    replace_str = replace_with_text if "replace" in operation else ""
                    match_count_total = 0

                    for pattern in patterns:
                        if use_regex:
                            found = re.findall(pattern, temp_processed_text, re.DOTALL)
                            all_found_matches.extend(found)
                            temp_processed_text, count = re.subn(pattern, replace_str, temp_processed_text, flags=re.DOTALL)
                            match_count_total += count
                        else:
                            count = temp_processed_text.count(pattern)
                            if count > 0:
                                all_found_matches.extend([pattern] * count)
                            temp_processed_text = temp_processed_text.replace(pattern, replace_str)
                            match_count_total += count
                    
                    if match_count_total == 0:
                         return handle_not_found(original_text_input, "Pattern not found for replacement")
                    
                    processed_output = temp_processed_text
                    remaining_output = "\n".join(all_found_matches) 
                    return (processed_output, remaining_output)

            elif "start text" in operation or "between" in operation:
                
                def get_index(txt, pattern, is_regex, is_end_search=False, start_from=0):
                    if is_regex:
                        match = re.search(pattern, txt[start_from:], re.DOTALL)
                        if not match: return -1, -1
                        return start_from + match.start(), start_from + match.end()
                    else:
                        idx = txt.find(pattern, start_from)
                        if idx == -1: return -1, -1
                        return idx, idx + len(pattern)

                if "start text" in operation:
                    if not start_text:
                        return handle_not_found(original_text_input, "start_text input is missing")
                    
                    s_start, s_end = get_index(text_to_process, start_text, use_regex)
                    
                    if s_start == -1:
                        return handle_not_found(original_text_input, f"Start text '{start_text}' not found")

                    split_point = s_start 

                    part_before = text_to_process[:split_point]
                    part_after = text_to_process[split_point:] 

                    if "extract before" in operation:
                        return (part_before, part_after)
                    elif "remove before" in operation: 
                        return (part_after, part_before)
                    elif "extract after" in operation:
                        return (part_after, part_before)
                    elif "remove after" in operation:
                        return (part_before, part_after)

                elif "between" in operation:
                    if not start_text or not end_text:
                        return handle_not_found(original_text_input, "start_text or end_text missing")

                    s_start, s_end = get_index(text_to_process, start_text, use_regex)
                    if s_start == -1:
                        return handle_not_found(original_text_input, f"Start text '{start_text}' not found")
                    
                    e_start, e_end = get_index(text_to_process, end_text, use_regex, start_from=s_end)
                    
                    if e_start == -1:
                        return handle_not_found(original_text_input, f"End text '{end_text}' not found after start")

                    target_text = text_to_process[s_end:e_start]
                    before_text = text_to_process[:s_end]
                    after_text = text_to_process[e_start:]

                    if operation == "extract between":
                        return (target_text, before_text + after_text)
                    else: # remove between
                        return (before_text + after_text, target_text)

        except re.error as e:
            print(f"[AdvancedTextFilter] Regex Error: {e}")
            return (original_text_input, f"REGEX ERROR: {e}")

        except Exception as e:
            print(f"[AdvancedTextFilter] Generic Error: {e}")
            return (original_text_input, str(e)) 

        return (text_to_process, "Unknown operation")
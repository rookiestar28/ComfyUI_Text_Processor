import re

class AdvancedTextFilter:
    """
    這個節點根據指定的操作，處理輸入文本，並提供兩個輸出：
    1. processed_text: 操作的主要結果。
    2. remaining_text: 另一個部分的文本。
    (v1.3 - 將 Find/Replace 與 Split/Between 的輸入欄位分開)
    """
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        
        # 更新 'find and replace' 的名稱以反映新輸入
        operation_modes = [
            # === 查找/替換/擷取 (使用 optional_text_input) ===
            "find and remove (use optional_text)",
            "find and replace (use optional_text, replace_with_text)",
            "find all (extract) (use optional_text)",
            
            # === 範圍 (Between) (使用 start_text, end_text) ===
            "extract between",
            "remove between",
            
            # === 分割 (Split) (使用 start_text) ===
            "extract before start text",
            "extract after start text",
            "remove before start text",
            "remove after start text",
            
            # === 清理 (Cleanup) ===
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
                
                # --- 專用於 Split/Between 操作 ---
                "start_text": ("STRING", {"multiline": False, "default": ""}),
                "end_text": ("STRING", {"multiline": False, "default": ""}),
                
                # --- 專用於 Find/Replace/Extract 操作 ---
                "optional_text_input": ("STRING", {"multiline": False, "default": "", "placeholder": "用於 Find... 可用 , 分隔多個"}),
                "replace_with_text": ("STRING", {"multiline": False, "default": "", "placeholder": "用於 Find and Replace"}),
                
                # --- 通用 ---
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

    # 更新 process 函式簽名，分離 'find' 和 'split' 的輸入
    def process(self, text, concat_mode, operation, 
                start_text, end_text,                     # 用於 Split/Between
                optional_text_input, replace_with_text,   # 用於 Find/Replace
                use_regex, case_conversion, 
                external_text=None):

        external_text_str = None
        if external_text is not None:
            external_text_str = str(external_text) 

        # 1. 預處理：合併文本
        text_to_process = text  
        if external_text_str and concat_mode != "disabled":
            if concat_mode == "prepend_external_text":
                text_to_process = external_text_str + text_to_process
            elif concat_mode == "append_external_text":
                text_to_process = text_to_process + external_text_str
        
        # 2. 預處理：大小寫轉換
        if case_conversion == "to UPPERCASE":
            text_to_process = text_to_process.upper()
        elif case_conversion == "to lowercase":
            text_to_process = text_to_process.lower()

        # 儲存此階段的文本，用於錯誤回退
        original_text_input = text_to_process
        
        
        try:
            if operation == "remove empty lines":
                lines = text_to_process.splitlines()
                processed_lines = [line for line in lines if line.strip()]
                return ("\n".join(processed_lines), "")

            if operation == "remove newlines":
                processed = text_to_process.replace("\r", "").replace("\n", "")
                return (processed, "")

            if operation == "strip lines (trim)":
                lines = text_to_process.splitlines()
                processed_lines = [line.strip() for line in lines]
                return ("\n".join(processed_lines), "")

            if operation == "remove all whitespace (keep newlines)":
                lines = text_to_process.splitlines()
                processed_lines = ["".join(line.split()) for line in lines]
                return ("\n".join(processed_lines), "")

            
            find_ops = [
                "find and remove (use optional_text)",
                "find and replace (use optional_text, replace_with_text)",
                "find all (extract) (use optional_text)"
            ]

            if operation in find_ops:
                # 這些操作現在 *只* 使用 optional_text_input
                if not optional_text_input:
                    if operation == "find all (extract) (use optional_text)":
                        return ("", original_text_input) 
                    else:
                        return (original_text_input, "") 

                # 根據 , 分隔符解析多個 pattern
                patterns = [p.strip() for p in optional_text_input.split(',') if p.strip()]
                if not patterns:
                     raise ValueError("optional_text_input is empty or contains only delimiters")

                processed_text = text_to_process
                all_found_matches = [] # 用於 'remaining_text'

                # 'find all (extract)' 需要一個獨立的列表
                if operation == "find all (extract) (use optional_text)":
                    for pattern in patterns:
                        if use_regex:
                            all_found_matches.extend(re.findall(pattern, processed_text))
                        else:
                            # 對於純文字，我們需要計算次數
                            count = processed_text.count(pattern)
                            if count > 0:
                                all_found_matches.extend([pattern] * count)
                    
                    # 處理 (processed_text) 是所有找到的匹配項
                    processed_output = "\n".join(all_found_matches)
                    
                    # 剩餘 (remaining_text) 是移除了所有匹配項的原始文本
                    remaining_output = text_to_process
                    for pattern in patterns:
                        if use_regex:
                            remaining_output = re.sub(pattern, "", remaining_output)
                        else:
                            remaining_output = remaining_output.replace(pattern, "")
                    
                    return (processed_output, remaining_output)

                else:
                    # 對於 'remove' 和 'replace'
                    temp_processed_text = text_to_process
                    
                    for pattern in patterns:
                        # 先收集被替換/移除的內容
                        if use_regex:
                            all_found_matches.extend(re.findall(pattern, temp_processed_text))
                        else:
                            count = temp_processed_text.count(pattern)
                            if count > 0:
                                all_found_matches.extend([pattern] * count)
                        
                        # 然後執行替換/移除
                        replace_str = ""
                        if operation == "find and replace (use optional_text, replace_with_text)":
                            replace_str = replace_with_text # 使用新輸入

                        if use_regex:
                            temp_processed_text = re.sub(pattern, replace_str, temp_processed_text)
                        else:
                            temp_processed_text = temp_processed_text.replace(pattern, replace_str)
                    
                    processed_output = temp_processed_text
                    remaining_output = "\n".join(all_found_matches)
                    return (processed_output, remaining_output)

            
            split_ops = [
                "extract before start text", "extract after start text",
                "remove before start text", "remove after start text"
            ]
            
            if operation in split_ops:
                if not start_text:
                    raise ValueError("start_text is required for this operation")
                
                split_index = -1
                
                if use_regex:
                    match = re.search(start_text, text_to_process)
                    if not match:
                        raise ValueError("Start text regex not found")
                    split_index = match.start()
                else:
                    split_index = text_to_process.find(start_text)
                    if split_index == -1:
                        raise ValueError("Start text not found")

                part_before = text_to_process[:split_index]
                part_after = text_to_process[split_index:]
                
                if operation == "extract before start text" or operation == "remove after start text":
                    return (part_before, part_after)
                
                if operation == "extract after start text" or operation == "remove before start text":
                    return (part_after, part_before)


            between_ops = ["extract between", "remove between"]
            if operation in between_ops:
                
                if not start_text or not end_text:
                    if operation == "extract between":
                        return ("", text_to_process)
                    else:
                        return (text_to_process, "")

                
                if use_regex:
                    start_match = re.search(start_text, text_to_process)
                    if not start_match:
                        raise ValueError("Start text regex not found in text")
                    
                    start_of_target = start_match.end()

                    end_match = re.search(end_text, text_to_process[start_of_target:])
                    if not end_match:
                        raise ValueError("End text regex not found after start text")

                    end_of_target = start_of_target + end_match.start()

                else:
                    start_index = text_to_process.find(start_text)
                    if start_index == -1:
                        raise ValueError("Start text not found in text")
                    
                    start_of_target = start_index + len(start_text)
                    
                    end_of_target = text_to_process.find(end_text, start_of_target)
                    if end_of_target == -1:
                        raise ValueError("End text not found after start delimiter")

                target_text = text_to_process[start_of_target:end_of_target]
                before_text = text_to_process[:start_of_target]
                after_text = text_to_process[end_of_target:]

                if operation == "extract between":
                    processed_output = target_text
                    remaining_output = before_text + after_text
                else: # "remove between"
                    processed_output = before_text + after_text
                    remaining_output = target_text
                
                return (processed_output, remaining_output)

        
        except ValueError as e:
            print(f"[AdvancedTextFilter] Warning: {e}")
            if operation.startswith("extract") or operation.startswith("find all"):
                return ("", original_text_input) 
            else:
                return (original_text_input, "") 
        
        except re.error as e:
            print(f"[AdvancedTextFilter] Regex Error: {e}")
            return (original_text_input, f"REGEX ERROR: {e}")

        except Exception as e:
            print(f"[AdvancedTextFilter] Error: {e}")
            return (original_text_input, str(e)) 

        # 備用
        return (text_to_process, "Unknown operation")
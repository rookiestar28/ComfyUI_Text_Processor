import os
import random
import re
import folder_paths


PLUGIN_WILDCARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wildcards')


def get_comfyui_base_path():
    return getattr(folder_paths, "base_path", os.getcwd())


def get_wildcard_dir():
    """Get or create the wildcards directory safely."""
    wildcard_path = os.path.join(get_comfyui_base_path(), 'wildcards')
    if not os.path.exists(wildcard_path):
        try:
            os.makedirs(wildcard_path, exist_ok=True)
        except Exception:
            pass
    return wildcard_path

def get_wildcard_dirs():
    """Return wildcard search roots in precedence order."""
    roots = [get_wildcard_dir(), PLUGIN_WILDCARD_DIR]
    unique_roots = []
    seen = set()
    for root in roots:
        real_root = os.path.realpath(root)
        if real_root not in seen:
            seen.add(real_root)
            unique_roots.append(real_root)
    return unique_roots

def _normalize_wildcard_name(wildcard_name):
    wildcard_name = str(wildcard_name).strip().replace('\\', '/')
    if wildcard_name.endswith('.txt'):
        wildcard_name = wildcard_name[:-4]
    wildcard_name = wildcard_name.strip('/')

    if not wildcard_name or os.path.isabs(wildcard_name):
        return None
    if re.search(r'[<>:"|?*\x00-\x1f]', wildcard_name):
        return None

    parts = wildcard_name.split('/')
    if any(part in {"", ".", ".."} for part in parts):
        return None

    return "/".join(parts)

def _is_within_directory(path, base_directory):
    try:
        base_directory = os.path.realpath(base_directory)
        path = os.path.realpath(path)
        return os.path.commonpath([path, base_directory]) == base_directory
    except (OSError, ValueError):
        return False

def resolve_wildcard_path(wildcard_name):
    normalized_name = _normalize_wildcard_name(wildcard_name)
    if normalized_name is None:
        return None

    relative_parts = normalized_name.split('/')
    for root in get_wildcard_dirs():
        candidate = os.path.realpath(os.path.join(root, *relative_parts) + ".txt")
        # CRITICAL: wildcard names are workflow-controlled; never allow traversal outside roots.
        if _is_within_directory(candidate, root) and os.path.exists(candidate):
            return candidate

    return None

def get_all_wildcards():
    """
    Scan for .txt files in all configured wildcard directories.
    """
    files_list = set()
    for wildcards_path in get_wildcard_dirs():
        if os.path.exists(wildcards_path):
            for root, dirs, files in os.walk(wildcards_path):
                dirs[:] = [d for d in dirs if d not in {".", ".."}]
                for file in files:
                    if file.endswith('.txt'):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, wildcards_path)
                        clean_name = os.path.splitext(rel_path)[0].replace('\\', '/')
                        normalized_name = _normalize_wildcard_name(clean_name)
                        if normalized_name:
                            files_list.add(normalized_name)
    return sorted(files_list)

def process_random_options(text, seed):
    """Handle {option1|option2} syntax."""
    rng = random.Random(seed)
    
    def replace_options(match):
        options = [opt.strip() for opt in match.group(1).split('|')]
        if not options: return ""
        selected = rng.choice(options)
        
        if '__' in selected or '{' in selected:
            return process_wildcard_syntax(selected, seed + 1)
        return selected
    
    return re.sub(r'\{([^{}]+)\}', replace_options, text)

def find_and_replace_wildcards(prompt, offset_seed, debug=False, recursion_depth=0):
    """Handle __wildcard__ syntax."""
    regex_pattern = r'__([^_\\/][^__]*?)__'
    
    wildcard_count = 0
    
    def replacement_func(match):
        nonlocal wildcard_count
        wildcard_name = match.group(1) 
        
        file_path = resolve_wildcard_path(wildcard_name)
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                
                if lines:
                    match_seed = offset_seed + wildcard_count
                    match_rng = random.Random(match_seed)
                    selected = match_rng.choice(lines)
                    
                    wildcard_count += 1
                    
                    if '__' in selected or '{' in selected:
                        return process_wildcard_syntax(selected, match_seed, debug, recursion_depth + 1)
                    return selected
            except Exception:
                pass
        
        return match.group(0)

    return re.sub(regex_pattern, replacement_func, prompt)

def process_wildcard_syntax(text, seed, debug=False, recursion_depth=0):
    """Main processing pipeline."""
    if recursion_depth > 10: # 防止無限迴圈
        return text
    if not text:
        return ""
        
    text = process_random_options(text, seed)
    text = find_and_replace_wildcards(text, seed, debug, recursion_depth)
    return text


class WildcardsNode:
    """
    Wildcards Node: 
    支援 '{a|b}' 隨機選擇與 '__file__' 通配符語法。
    提供文字輸入框與檔案下拉選單，兩者可混合使用。
    """
    RETURN_TYPES = ('STRING',)
    FUNCTION = 'process'
    CATEGORY = "ComfyUI Text Processor"

    @classmethod
    def INPUT_TYPES(cls):
        wildcard_files = get_all_wildcards()
        wildcard_options = ["None", "Random"] + wildcard_files
        
        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "prompt_1": ("STRING", {"multiline": True, "dynamicPrompts": False}),
                "wildcard_1": (wildcard_options,),
                "prompt_2": ("STRING", {"multiline": True, "dynamicPrompts": False}),
                "wildcard_2": (wildcard_options,),
                "prompt_3": ("STRING", {"multiline": True, "dynamicPrompts": False}),
                "wildcard_3": (wildcard_options,),
                "prompt_4": ("STRING", {"multiline": True, "dynamicPrompts": False}),
                "wildcard_4": (wildcard_options,),
                "prompt_5": ("STRING", {"multiline": True, "dynamicPrompts": False}),
                "wildcard_5": (wildcard_options,),
                "prompt_6": ("STRING", {"multiline": True, "dynamicPrompts": False}),
                "wildcard_6": (wildcard_options,),
                "prompt_7": ("STRING", {"multiline": True, "dynamicPrompts": False}),
                "wildcard_7": (wildcard_options,),
            }
        }
    
    def process(self, seed, **kwargs):
        offsets = [0, 144, 245, 283, 483, 747, -969]
        final_parts = []
        
        for i in range(1, 8):
            prompt_key = f"prompt_{i}"
            wildcard_key = f"wildcard_{i}"
            
            prompt_text = kwargs.get(prompt_key, "")
            wildcard_selection = kwargs.get(wildcard_key, "None")
            
            current_seed = seed + offsets[(i-1) % len(offsets)]
            
            processed_text = process_wildcard_syntax(prompt_text, current_seed)
            
            wildcard_text = ""
            if wildcard_selection != "None":
                wc_seed = current_seed + 5 
                rng = random.Random(wc_seed)
                
                target = wildcard_selection
                if target == "Random":
                    all_files = get_all_wildcards()
                    if all_files:
                        target = rng.choice(all_files)
                    else:
                        target = None
                
                if target:
                    dummy = f"__{target}__"
                    wildcard_text = process_wildcard_syntax(dummy, wc_seed)
            
            combined = f"{processed_text} {wildcard_text}".strip()
            if combined:
                final_parts.append(combined)
        
        return (" ".join(final_parts),)


NODE_CLASS_MAPPINGS = {
    "WildcardsNode": WildcardsNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "WildcardsNode": "Wildcards Processor"
}

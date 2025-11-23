import os
import random
import re
import folder_paths


def get_wildcard_dir():
    """Get or create the wildcards directory safely."""
    wildcard_path = os.path.join(folder_paths.base_path, 'wildcards')
    if not os.path.exists(wildcard_path):
        try:
            os.makedirs(wildcard_path, exist_ok=True)
        except Exception:
            pass
    return wildcard_path

def get_all_wildcards():
    """
    Scan for .txt files in the wildcards directory.
    (優化：包含相對路徑，例如 'style/cyberpunk')
    """
    wildcards_path = get_wildcard_dir()
    files_list = []
    if os.path.exists(wildcards_path):
        for root, dirs, files in os.walk(wildcards_path):
            for file in files:
                if file.endswith('.txt'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, wildcards_path)
                    clean_name = os.path.splitext(rel_path)[0].replace('\\', '/')
                    files_list.append(clean_name)
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
        
        base_dir = get_wildcard_dir()
        
        file_path = os.path.join(base_dir, f"{wildcard_name}.txt")
        
        if os.path.exists(file_path):
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


class Wildcards:
    """
    Basic Wildcards Node: Simple text inputs only.
    """
    RETURN_TYPES = ('STRING',)
    FUNCTION = 'star_wilds'
    CATEGORY = "Text Processor"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "prompt_1": ("STRING", {"multiline": True}),
                "prompt_2": ("STRING", {"multiline": True}),
                "prompt_3": ("STRING", {"multiline": True}),
                "prompt_4": ("STRING", {"multiline": True}),
                "prompt_5": ("STRING", {"multiline": True}),
                "prompt_6": ("STRING", {"multiline": True}),
                "prompt_7": ("STRING", {"multiline": True}),
            }
        }
    
    def star_wilds(self, seed, **kwargs):
        offsets = [0, 144, 245, 283, 483, 747, -969]
        final_parts = []
        
        for i in range(1, 8):
            prompt_key = f"prompt_{i}"
            prompt_text = kwargs.get(prompt_key, "")
            
            if prompt_text.strip():
                current_seed = seed + offsets[(i-1) % len(offsets)]
                processed = process_wildcard_syntax(prompt_text, current_seed)
                if processed.strip():
                    final_parts.append(processed)
        
        return (" ".join(final_parts),)


class WildcardsAdv:
    """
    Advanced Wildcards Node: Includes dropdown menus for file selection.
    """
    RETURN_TYPES = ('STRING',)
    FUNCTION = 'star_wilds_adv'
    CATEGORY = "Text Processor"

    @classmethod
    def INPUT_TYPES(cls):
        wildcard_files = get_all_wildcards()
        wildcard_options = ["None", "Random"] + wildcard_files
        
        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "prompt_1": ("STRING", {"multiline": True}),
                "wildcard_1": (wildcard_options,),
                "prompt_2": ("STRING", {"multiline": True}),
                "wildcard_2": (wildcard_options,),
                "prompt_3": ("STRING", {"multiline": True}),
                "wildcard_3": (wildcard_options,),
                "prompt_4": ("STRING", {"multiline": True}),
                "wildcard_4": (wildcard_options,),
                "prompt_5": ("STRING", {"multiline": True}),
                "wildcard_5": (wildcard_options,),
                "prompt_6": ("STRING", {"multiline": True}),
                "wildcard_6": (wildcard_options,),
                "prompt_7": ("STRING", {"multiline": True}),
                "wildcard_7": (wildcard_options,),
            }
        }
    
    def star_wilds_adv(self, seed, **kwargs):
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
    "Wildcards": Wildcards,
    "WildcardsAdv": WildcardsAdv
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Wildcards": "Wildcards Node (Simple)",
    "WildcardsAdv": "Wildcards Node (Advanced)"
}
import os
import json
import time
import re
import glob
from datetime import datetime

class SimpleFileLock:

    def __init__(self, lock_file, timeout=10, delay=0.05):
        self.lock_file = lock_file + ".lock"
        self.timeout = timeout
        self.delay = delay

    def __enter__(self):
        start_time = time.time()
        while True:
            try:
                fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return self
            except FileExistsError:
                if time.time() - start_time >= self.timeout:
                    print(f"[TextStorage] Error: Could not acquire lock for {self.lock_file} after {self.timeout}s.")
                    try:
                        os.remove(self.lock_file)
                    except:
                        pass
                    continue
                time.sleep(self.delay)

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except OSError:
            pass

class TextStorageHandler:
    storage_version = 0
    
    def __init__(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.storage_dir = os.path.join(base_path, "text_storage")
        self.json_file = os.path.join(self.storage_dir, "text_storage.json")
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)
        if not os.path.exists(self.json_file):
            with SimpleFileLock(self.json_file):
                with open(self.json_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=2)

    def _sanitize_filename(self, name):
        return re.sub(r'[\\/?:|"<>]+', "", name).strip()

    def load_json_data(self):
        try:
            if os.path.exists(self.json_file):
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
        return {}

    def get_all_keys(self):
        keys = set()
        json_data = self.load_json_data()
        keys.update(json_data.keys())
        
        txt_files = glob.glob(os.path.join(self.storage_dir, "*.txt"))
        for f in txt_files:
            filename = os.path.basename(f)
            name_without_ext = os.path.splitext(filename)[0]
            keys.add(name_without_ext)
            
        return sorted(list(keys))

    def read_content(self, key):
        safe_name = key 
        txt_path = os.path.join(self.storage_dir, f"{safe_name}.txt")
        
        if os.path.exists(txt_path):
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    print(f"[TextReader] Loaded from TXT: {safe_name}.txt")
                    return f.read()
            except Exception as e:
                print(f"[TextReader] Error reading txt: {e}")
        
        json_data = self.load_json_data()
        if key in json_data:
            print(f"[TextReader] Loaded from JSON key: {key}")
            return json_data[key]
        return ""

    def _parse_time_tags(self, pattern):
        if "%" in pattern:
            try:
                now = datetime.now()
                return now.strftime(pattern)
            except Exception:
                return pattern
        return pattern

    def resolve_naming_conflict(self, pattern, existing_keys):
        base_name = self._parse_time_tags(pattern)
        
        match = re.search(r"(\*+)", base_name)
        if match:
            star_group = match.group(1)
            width = len(star_group)
            
            counter = 1
            while True:
                number_str = str(counter).zfill(width)
                candidate = base_name.replace(star_group, number_str, 1)
                
                if candidate not in existing_keys:
                    return candidate
                counter += 1
        else:
            if base_name not in existing_keys:
                return base_name
            counter = 1
            while f"{base_name}_{counter}" in existing_keys:
                counter += 1
            return f"{base_name}_{counter}"

    def save_text(self, prefix, name, content, mode="add", storage_format="json"):
        if not name and not prefix:
            print("[TextStorage] Error: No name or prefix provided.")
            return

        raw_full_name = f"{prefix}{name}"
        clean_pattern = self._sanitize_filename(raw_full_name)

        with SimpleFileLock(self.json_file, timeout=10):
            
            current_keys = self.get_all_keys()
            final_name = clean_pattern

            if mode == "delete":
                target_name = clean_pattern
                deleted = False
                
                txt_path = os.path.join(self.storage_dir, f"{target_name}.txt")
                if os.path.exists(txt_path):
                    try:
                        os.remove(txt_path)
                        print(f"[TextStorage] Deleted file: {target_name}.txt")
                        deleted = True
                    except Exception as e:
                        print(f"[TextStorage] Error deleting txt: {e}")

                data = self.load_json_data()
                if target_name in data:
                    del data[target_name]
                    with open(self.json_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    print(f"[TextStorage] Deleted key from JSON: {target_name}")
                    deleted = True
                
                if not deleted:
                    print(f"[TextStorage] Warning: '{target_name}' not found.")

            else:
                if mode == "add":
                    final_name = self.resolve_naming_conflict(clean_pattern, current_keys)
                    if final_name != clean_pattern.replace("*", "1"): 
                        print(f"[TextStorage] Auto-named: '{final_name}'")
                else:
                    temp_name = self._parse_time_tags(clean_pattern)
                    match = re.search(r"(\*+)", temp_name)
                    if match:
                        width = len(match.group(1))
                        final_name = temp_name.replace(match.group(1), "1".zfill(width), 1)
                    else:
                        final_name = temp_name
                    print(f"[TextStorage] Overwriting: '{final_name}'")

                if storage_format == "txt":
                    txt_path = os.path.join(self.storage_dir, f"{final_name}.txt")
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"[TextStorage] Saved to TXT: {final_name}.txt")
                    
                else: # json
                    data = self.load_json_data()
                    data[final_name] = content
                    with open(self.json_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    print(f"[TextStorage] Saved to JSON: {final_name}")

        TextStorageHandler.storage_version += 1


class TextStorageReader:
    def __init__(self):
        self.handler = TextStorageHandler()
    @classmethod
    def INPUT_TYPES(cls):
        handler = TextStorageHandler()
        keys = handler.get_all_keys()
        return {"required": {"text_key": (sorted(keys),)}}
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text_content",)
    FUNCTION = "read_text"
    CATEGORY = "ComfyUI Text Processor"
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return TextStorageHandler.storage_version
    def read_text(self, text_key):
        if text_key == "No texts saved yet": return ("",)
        return (self.handler.read_content(text_key),)

class TextStorageWriter:
    def __init__(self):
        self.handler = TextStorageHandler()
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text_input": ("STRING", {"multiline": True, "forceInput": True}),
                "filename_prefix": ("STRING", {"default": ""}),
                "save_name": ("STRING", {"default": "My_Data"}),
                "mode": (["Add New (Auto Rename)", "Overwrite Existing", "Delete"],),
                "storage_format": (["json", "txt"], {"default": "json"}),
            }
        }
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("passthrough_text",)
    OUTPUT_NODE = True
    FUNCTION = "write_text"
    CATEGORY = "ComfyUI Text Processor"
    def write_text(self, text_input, filename_prefix, save_name, mode, storage_format):
        action = "add"
        if mode == "Overwrite Existing": action = "overwrite"
        elif mode == "Delete": action = "delete"
        self.handler.save_text(filename_prefix, save_name, text_input, action, storage_format)
        return (text_input,)

NODE_CLASS_MAPPINGS = {
    "TextStorageReader": TextStorageReader,
    "TextStorageWriter": TextStorageWriter
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "TextStorageReader": "Text Storage (Reader)",
    "TextStorageWriter": "Text Storage (Writer)"
}
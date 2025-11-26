import os
import json
import time
import re
import glob

class SimpleFileLock:
    def __init__(self, lock_file, timeout=5, delay=0.1):
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
                    raise TimeoutError(f"Could not acquire lock for {self.lock_file}")
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
            
        sorted_keys = sorted(list(keys))
        return sorted_keys if sorted_keys else ["No texts saved yet"]

    def read_content(self, key):
        safe_name = key.replace("*", "_") 
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

    def get_unique_name_with_wildcard(self, pattern, existing_keys):
        if "*" not in pattern:
            if pattern not in existing_keys:
                return pattern
            counter = 1
            while f"{pattern}_{counter}" in existing_keys:
                counter += 1
            return f"{pattern}_{counter}"
        
        counter = 1
        while True:
            candidate = pattern.replace("*", str(counter))
            if candidate not in existing_keys:
                return candidate
            counter += 1

    def save_text(self, prefix, name, content, mode="add", storage_format="json"):
        if not name and not prefix:
            print("[TextStorage] Error: No name or prefix provided.")
            return

        raw_full_name = f"{prefix}{name}"
        
        clean_pattern = self._sanitize_filename(raw_full_name)
        
        current_keys = self.get_all_keys()
        final_name = clean_pattern
        
        if mode == "delete":
            target_name = clean_pattern.replace("*", "_")
            deleted = False
            
            txt_path = os.path.join(self.storage_dir, f"{target_name}.txt")
            if os.path.exists(txt_path):
                try:
                    with SimpleFileLock(txt_path):
                        os.remove(txt_path)
                    print(f"[TextStorage] Deleted file: {target_name}.txt")
                    deleted = True
                except Exception as e:
                    print(f"[TextStorage] Error deleting txt: {e}")

            with SimpleFileLock(self.json_file):
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
                final_name = self.get_unique_name_with_wildcard(clean_pattern, current_keys)
                if final_name != clean_pattern.replace("*", "1"):
                     print(f"[TextStorage] Auto-named: '{final_name}'")
            else:
                final_name = clean_pattern.replace("*", "1")

            if storage_format == "txt":
                txt_path = os.path.join(self.storage_dir, f"{final_name}.txt")
                with SimpleFileLock(txt_path):
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                print(f"[TextStorage] Saved to TXT: {final_name}.txt")
                
            else: # json
                with SimpleFileLock(self.json_file):
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
        return {
            "required": {
                "text_key": (sorted(keys),),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text_content",)
    FUNCTION = "read_text"
    CATEGORY = "ComfyUI Text Processor"
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return TextStorageHandler.storage_version

    def read_text(self, text_key):
        if text_key == "No texts saved yet":
            return ("",)
        content = self.handler.read_content(text_key)
        return (content,)


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
        if mode == "Overwrite Existing":
            action = "overwrite"
        elif mode == "Delete":
            action = "delete"
        
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
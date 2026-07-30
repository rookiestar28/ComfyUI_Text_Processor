import os
import json
import time
import re
import glob
from datetime import datetime
from importlib import import_module


PLUGIN_STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "text_storage")
USER_STORAGE_SUBDIR = os.path.join("ComfyUI_Text_Processor", "text_storage")


def _resolve_user_storage_dir():
    try:
        folder_paths = import_module("folder_paths")
        get_user_directory = getattr(folder_paths, "get_user_directory", None)
        if callable(get_user_directory):
            user_dir = get_user_directory()
            if user_dir:
                return os.path.join(user_dir, USER_STORAGE_SUBDIR)
    except Exception:
        pass
    return None

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
        self.legacy_storage_dir = PLUGIN_STORAGE_DIR
        self.storage_dir = _resolve_user_storage_dir() or self.legacy_storage_dir
        self.json_file = os.path.join(self.storage_dir, "text_storage.json")
        self.legacy_json_file = os.path.join(self.legacy_storage_dir, "text_storage.json")
        self._ensure_storage_exists()

    def _storage_dirs(self):
        dirs = []
        for storage_dir in [getattr(self, "storage_dir", None), getattr(self, "legacy_storage_dir", None)]:
            if not storage_dir:
                continue
            real_dir = os.path.realpath(storage_dir)
            if real_dir not in dirs:
                dirs.append(real_dir)
        return dirs

    def _json_file_for_dir(self, storage_dir):
        if os.path.realpath(storage_dir) == os.path.realpath(getattr(self, "storage_dir", "")):
            return self.json_file
        return os.path.join(storage_dir, "text_storage.json")
    
    def _ensure_storage_exists(self):
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)
        if not os.path.exists(self.json_file):
            with SimpleFileLock(self.json_file):
                with open(self.json_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=2)

    def _sanitize_filename(self, name):
        return re.sub(r'[\\/?:|"<>]+', "", name).strip()

    def _load_json_file(self, json_file):
        try:
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
        return {}

    def load_json_data(self):
        return self._load_json_file(self.json_file)

    def get_all_keys(self):
        keys = set()
        for storage_dir in self._storage_dirs():
            json_data = self._load_json_file(self._json_file_for_dir(storage_dir))
            keys.update(json_data.keys())

            txt_files = glob.glob(os.path.join(storage_dir, "*.txt"))
            for f in txt_files:
                filename = os.path.basename(f)
                name_without_ext = os.path.splitext(filename)[0]
                keys.add(name_without_ext)
            
        return sorted(list(keys))

    def read_content(self, key):
        safe_name = key 
        for storage_dir in self._storage_dirs():
            txt_path = os.path.join(storage_dir, f"{safe_name}.txt")

            if os.path.exists(txt_path):
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        print(f"[TextReader] Loaded from TXT: {safe_name}.txt")
                        return f.read()
                except Exception as e:
                    print(f"[TextReader] Error reading txt: {e}")

            json_data = self._load_json_file(self._json_file_for_dir(storage_dir))
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

                for storage_dir in self._storage_dirs():
                    txt_path = os.path.join(storage_dir, f"{target_name}.txt")
                    if os.path.exists(txt_path):
                        try:
                            os.remove(txt_path)
                            print(f"[TextStorage] Deleted file: {target_name}.txt")
                            deleted = True
                        except Exception as e:
                            print(f"[TextStorage] Error deleting txt: {e}")

                    json_file = self._json_file_for_dir(storage_dir)
                    data = self._load_json_file(json_file)
                    if target_name in data:
                        del data[target_name]
                        with open(json_file, 'w', encoding='utf-8') as f:
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
        if not keys:
            keys = ["No texts saved yet"]
        return {
            "required": {
                "text_key": (
                    sorted(keys),
                    {"tooltip": "Saved Text Storage entry to read."},
                )
            }
        }
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text_content",)
    FUNCTION = "read_text"
    CATEGORY = "ComfyUI Text Processor"
    DESCRIPTION = "Reads saved text entries from the Text Storage JSON or TXT store."
    SEARCH_ALIASES = ["text storage reader", "read saved text", "load text", "clipboard reader"]
    OUTPUT_TOOLTIPS = ("Stored text content for the selected key.",)
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
                "text_input": ("STRING", {
                    "multiline": True,
                    "forceInput": True,
                    "tooltip": "Text to store and pass through; Delete mode ignores its content.",
                }),
                "filename_prefix": ("STRING", {
                    "default": "",
                    "tooltip": "Optional prefix added before the saved entry name.",
                }),
                "save_name": ("STRING", {
                    "default": "My_Data",
                    "tooltip": "Logical name of the entry to add, overwrite, or delete.",
                }),
                "mode": (
                    ["Add New (Auto Rename)", "Overwrite Existing", "Delete"],
                    {"tooltip": "Add with collision-safe renaming, overwrite the named entry, or delete it."},
                ),
                "storage_format": (
                    ["json", "txt"],
                    {
                        "default": "json",
                        "tooltip": "Store the entry in the JSON collection or as an individual text file.",
                    },
                ),
            }
        }
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("passthrough_text",)
    OUTPUT_NODE = True
    FUNCTION = "write_text"
    CATEGORY = "ComfyUI Text Processor"
    DESCRIPTION = "Writes, overwrites, auto-renames, or deletes text entries in Text Storage."
    SEARCH_ALIASES = ["text storage writer", "save text", "write text", "clipboard writer"]
    OUTPUT_TOOLTIPS = ("Passthrough copy of the text input.",)
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

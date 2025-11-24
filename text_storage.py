import os
import json

class TextStorageHandler:
    storage_version = 0
    
    def __init__(self):
        self.storage_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "text_storage.json")
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        if not os.path.exists(self.storage_file):
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
    
    def load_storage(self):
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def get_all_keys(self):
        data = self.load_storage()
        keys = list(data.keys())
        return keys if keys else ["No texts saved yet"]

    def get_unique_name(self, base_name, storage):
        if base_name not in storage:
            return base_name
        counter = 1
        while f"{base_name}_{counter}" in storage:
            counter += 1
        return f"{base_name}_{counter}"

    def save_text(self, name, content, mode="add"):
        """
        mode: 'add' (auto rename), 'overwrite', 'delete'
        """
        if not name or not name.strip():
            print("[TextStorage] Error: No name provided.")
            return

        storage = self.load_storage()
        
        if mode == "delete":
            if name in storage:
                del storage[name]
                print(f"[TextStorage] Deleted '{name}'")
            else:
                print(f"[TextStorage] Warning: '{name}' not found, cannot delete.")
        
        elif mode == "overwrite":
            storage[name] = content
            print(f"[TextStorage] Overwritten '{name}'")
            
        else: # add (default)
            final_name = self.get_unique_name(name, storage)
            storage[final_name] = content
            if final_name != name:
                print(f"[TextStorage] Name exists. Saved as '{final_name}'")
            else:
                print(f"[TextStorage] Saved '{final_name}'")

        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(storage, f, indent=2)
        
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
    CATEGORY = "Text Processor"
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return TextStorageHandler.storage_version

    def read_text(self, text_key):
        if text_key == "No texts saved yet":
            return ("",)
            
        data = self.handler.load_storage()
        content = data.get(text_key, "")
        print(f"[TextReader] Loaded: {text_key}")
        return (content,)


class TextStorageWriter:

    def __init__(self):
        self.handler = TextStorageHandler()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text_input": ("STRING", {"multiline": True, "forceInput": True}), # 強制輸入，避免 UI 混淆
                "save_name": ("STRING", {"default": "My_Data"}),
                "mode": (["Add New (Auto Rename)", "Overwrite Existing", "Delete"],),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("passthrough_text",)
    OUTPUT_NODE = True
    FUNCTION = "write_text"
    CATEGORY = "Text Processor"

    def write_text(self, text_input, save_name, mode):
        action = "add"
        if mode == "Overwrite Existing":
            action = "overwrite"
        elif mode == "Delete":
            action = "delete"
        
        self.handler.save_text(save_name, text_input, action)
        
        return (text_input,)


NODE_CLASS_MAPPINGS = {
    "TextStorageReader": TextStorageReader,
    "TextStorageWriter": TextStorageWriter
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TextStorageReader": "Text Storage (Reader)",
    "TextStorageWriter": "Text Storage (Writer)"
}
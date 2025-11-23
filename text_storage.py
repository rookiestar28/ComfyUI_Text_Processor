import os
import json
import copy

class TextStorage:
    storage_version = 0
    
    def __init__(self):
        self.storage_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "text_storage.json")
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        """Create the storage file if it doesn't exist."""
        if not os.path.exists(self.storage_file):
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
    
    def _load_storage(self):
        """Load the text storage database."""
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
            return {}
    
    @classmethod
    def INPUT_TYPES(cls):
        instance = cls()
        saved_texts = list(instance._load_storage().keys())
        
        if not saved_texts:
            saved_texts = ["No texts saved yet"]
        
        return {
            "required": {
                "mode": (["Save Text", "Load Text", "Remove Text", "Replace Text"], {"default": "Load Text"}),
                "Save-Name": ("STRING", {"default": "My Text"}),
            },
            "optional": {
                "Text-Selector": (saved_texts, {"default": saved_texts[0] if saved_texts else ""}),
                "text_content": ("STRING", {"multiline": True, "default": ""}),
            }
        }
        
    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    OUTPUT_NODE = True
    FUNCTION = "process_text"
    CATEGORY = "Text Processor"

    def process_text(self, mode, **kwargs):
        save_name = kwargs.get("Save-Name", "")
        text_content = kwargs.get("text_content", "")
        text_selector = kwargs.get("Text-Selector", "")
        
        
        if mode == "Save Text":
            return self._save_text(save_name, text_content)
            
        elif mode == "Load Text":
            target_name = text_selector if (text_selector and text_selector != "No texts saved yet") else save_name
            return self._load_text(target_name)
            
        elif mode == "Replace Text":
            target_name = text_selector if (text_selector and text_selector != "No texts saved yet") else save_name
            return self._replace_text(target_name, text_content)
            
        else:  # Remove Text
            target_name = text_selector if (text_selector and text_selector != "No texts saved yet") else save_name
            return self._remove_text(target_name)
    
    def _get_unique_name(self, base_name, storage):
        if base_name not in storage:
            return base_name
        counter = 1
        while f"{base_name}_{counter}" in storage:
            counter += 1
        return f"{base_name}_{counter}"
    
    def _save_text(self, text_name, text_content):
        """保存文本，並返回該文本內容以便後續使用"""
        if not text_name.strip():
            print("[TextStorage] Error: No name provided for save.")
            return (text_content,) # 返回內容，不中斷流
        
        storage = self._load_storage()
        
        original_name = text_name
        text_name = self._get_unique_name(text_name, storage)
        
        storage[text_name] = text_content
        
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(storage, f, indent=2)
        
        TextStorage.storage_version += 1
        
        if text_name != original_name:
            print(f"[TextStorage] Saved as '{text_name}' (original name taken).")
        else:
            print(f"[TextStorage] Saved '{text_name}' successfully.")
            
        return (text_content,)
    
    def _load_text(self, text_name):
        """讀取文本"""
        storage = self._load_storage()
        
        if text_name in storage:
            print(f"[TextStorage] Loaded '{text_name}'.")
            return (storage[text_name],)
        else:
            print(f"[TextStorage] Warning: Text '{text_name}' not found.")
            return ("",)
    
    def _remove_text(self, text_name):
        """刪除文本"""
        storage = self._load_storage()
        
        if text_name not in storage:
            print(f"[TextStorage] Warning: Cannot remove '{text_name}', not found.")
            return ("",)
        
        del storage[text_name]
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(storage, f, indent=2)
            
        TextStorage.storage_version += 1
        print(f"[TextStorage] Removed '{text_name}'.")
        
        return ("",)
                
    def _replace_text(self, text_name, text_content):
        """替換/更新文本"""
        if not text_name.strip():
            print("[TextStorage] Error: No name provided for replace.")
            return ("",)
            
        storage = self._load_storage()
        
        if text_name not in storage:
            print(f"[TextStorage] Error: Text '{text_name}' not found, cannot replace.")
            return ("",)
        
        storage[text_name] = text_content
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(storage, f, indent=2)
        
        TextStorage.storage_version += 1
        print(f"[TextStorage] Replaced content for '{text_name}'.")
        
        return (text_content,)

    @classmethod
    def IS_CHANGED(cls, mode, **kwargs):
        return cls.storage_version
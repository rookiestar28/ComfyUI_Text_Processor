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
            # 若文件損壞或不存在，返回空字典並重建文件
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
            return {}
    
    @classmethod
    def INPUT_TYPES(cls):
        # 實例化以讀取現有存儲的 Key，用於生成下拉選單
        instance = cls()
        saved_texts = list(instance._load_storage().keys())
        
        # 防呆：若無數據，提供預設選項
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
        mode = kwargs.get("mode", "Load Text")
        if mode == "Save Text":
            return True
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
        
        # 根據模式分發處理邏輯
        if mode == "Save Text":
            return self._save_text(save_name, text_content)
        elif mode == "Load Text":
            if text_selector and text_selector != "No texts saved yet":
                save_name = text_selector
            return self._load_text(save_name)
        elif mode == "Replace Text":
            if text_selector and text_selector != "No texts saved yet":
                save_name = text_selector
            return self._replace_text(save_name, text_content)
        else:  # Remove Text
            if text_selector and text_selector != "No texts saved yet":
                save_name = text_selector
            return self._remove_text(save_name)
    
    def _get_unique_name(self, base_name, storage):
        """Generate a unique name if duplication exists."""
        if base_name not in storage:
            return base_name
        
        counter = 1
        while f"{base_name}_{counter}" in storage:
            counter += 1
        
        return f"{base_name}_{counter}"
    
    def _save_text(self, text_name, text_content):
        """Save text to storage."""
        if not text_name.strip():
            return ("Error: Please provide a name for your text.",)
        
        storage = self._load_storage()
        
        # 確保名稱唯一性
        original_name = text_name
        text_name = self._get_unique_name(text_name, storage)
        
        # 更新數據
        storage[text_name] = text_content
        
        # 寫入文件
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(storage, f, indent=2)
        
        # 更新版本號 (修復了此處原本的 NameError)
        TextStorage.storage_version += 1
        
        if text_name != original_name:
            return (f"Text saved as '{text_name}' (original name '{original_name}' was already taken).",)
        else:
            return (f"Text '{text_name}' saved successfully.",)
    
    def _load_text(self, text_name):
        """Load text from storage."""
        storage = self._load_storage()
        
        if text_name in storage:
            return (storage[text_name],)
        else:
            available = list(storage.keys())
            if available:
                return (f"Text '{text_name}' not found. Available: {', '.join(available)}",)
            else:
                return ("No texts found. Please save text first.",)
    
    def _remove_text(self, text_name):
        """Remove text from storage."""
        storage = self._load_storage()
        
        if text_name not in storage:
            return (f"Text '{text_name}' not found.",)
        
        # 刪除並寫回
        del storage[text_name]
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(storage, f, indent=2)
            
        # 更新版本號 (修復了此處原本的 NameError)
        TextStorage.storage_version += 1
        return (f"Text '{text_name}' removed successfully.",)
                
    def _replace_text(self, text_name, text_content):
        """Replace text content."""
        if not text_name.strip() or not text_content.strip():
            return ("Error: Name or content missing.",)
        
        storage = self._load_storage()
        
        if text_name not in storage:
            return (f"Text '{text_name}' not found. Cannot replace.",)
        
        # 更新並寫回
        storage[text_name] = text_content
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(storage, f, indent=2)
        
        # 更新版本號 (修復了此處原本的 NameError)
        TextStorage.storage_version += 1
        return (f"Text '{text_name}' replaced successfully.",)

    @classmethod
    def IS_CHANGED(cls, mode, **kwargs):
        # 透過返回版本號，強制 ComfyUI 在數據變更時重新執行此節點
        return cls.storage_version

NODE_CLASS_MAPPINGS = {
    "TextStorage": TextStorage
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TextStorage": "Text Storage Node"
}
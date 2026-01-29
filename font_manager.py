import logging
from pathlib import Path
from typing import Tuple, List

# 已移除對 folder_paths 的依賴，改用標準庫 pathlib 處理相對路徑
from PIL.ImageFont import FreeTypeFont, load_default as load_default_font, truetype as load_truetype

class FontCollection(dict):
    """
    A dictionary that maps font names to PIL font objects.
    """

    def __init__(self):
        """
        Initialize the FontCollection.
        It automatically looks for a 'fonts' directory in the same folder as this script.
        """
        # [關鍵修改] 使用相對路徑動態定位
        # 無論您的插件資料夾叫 "ComfyUI_Text_Processor" 還是其他名字，都能正確找到同層級的 fonts 資料夾
        current_dir = Path(__file__).parent
        font_directory = current_dir / "fonts"

        logging.info(f"[FontCollection] Initializing FontCollection.")
        logging.info(f"[FontCollection] Looking for fonts in: {font_directory.resolve()}")

        paths: List[Path] = []
        if not font_directory.exists():
            # 如果 fonts 資料夾不存在，嘗試建立它，方便使用者放入字型
            try:
                font_directory.mkdir(parents=True, exist_ok=True)
                logging.info(f"[FontCollection] Created missing fonts directory at: {font_directory.resolve()}")
            except Exception as e:
                logging.warning(f"[FontCollection] Font directory missing and could not be created: {e}")
        else:
            # 掃描 .ttf 和 .otf 檔案 (大小寫不敏感)，並避免在 Windows 上因為檔案系統
            # 大小寫不敏感導致同一檔案被重複計數/載入 (例如 *.ttf 與 *.TTF)。
            candidates: List[Path] = []
            for f in font_directory.rglob("*"):
                if f.is_file() and f.suffix.lower() in (".ttf", ".otf"):
                    candidates.append(f)

            seen: set[str] = set()
            for f in candidates:
                key = str(f.resolve()).replace("\\", "/").casefold()
                if key in seen:
                    continue
                seen.add(key)
                paths.append(f)
        
        logging.info(f"[FontCollection] Found {len(paths)} font files.")

        # 初始化字典
        fonts = {}

        # 1. 先載入預設字型作為保底
        try:
            self.default_font_name, self.default_font = self.load_default_font()
            fonts[self.default_font_name] = self.default_font
            logging.info(f"[FontCollection] Loaded internal default font: {self.default_font_name}")
        except Exception as e:
            logging.error(f"[FontCollection] Failed to load internal default font: {e}")
            self.default_font_name = "Error_No_Font"
            self.default_font = None

        # 2. 載入自定義字型
        for path in paths:
            try:
                font_info = self.load_font(path)
                if font_info:
                    font_name, font_obj = font_info
                    if font_name in fonts:
                        logging.warning(f"[FontCollection] Duplicate font name '{font_name}' found in {path.name}. Overwriting previous one.")
                    fonts[font_name] = font_obj
            except Exception as e:
                logging.error(f"[FontCollection] Failed to load font from {path.name}: {e}")
        
        super().__init__(fonts)
        logging.info(f"[FontCollection] Initialization complete. Total fonts available: {len(self)}")

    @classmethod
    def load_default_font(cls) -> Tuple[str, FreeTypeFont]:
        """
        Load the default PIL font.
        """
        font = load_default_font()
        # 確保類型正確
        if not isinstance(font, FreeTypeFont):
            pass 
        
        name_tuple = font.getname()
        if name_tuple:
            family, style = name_tuple
        else:
            family, style = "DefaultPillowFont", "Regular"

        family = family or "UnknownDefaultFamily"
        style = style or "Regular"
        return " ".join([family, style]), font

    @classmethod
    def load_font(cls, path: Path) -> Tuple[str, FreeTypeFont]:
        """
        Load a font and extract its name and style.
        """
        # size=10 只是初始載入，後續 AddTextToImage 會使用 font_variant 動態調整大小
        font = load_truetype(str(path), size=10) 
        
        name_tuple = font.getname()
        if name_tuple:
            family, style = name_tuple
        else:
            family, style = path.stem, "Regular"

        family = family or path.stem
        style = style or "Regular"
        
        if family == style:
            return family, font
        return " ".join([family, style]), font

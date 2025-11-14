import logging
from pathlib import Path
from typing import Tuple

from PIL.ImageFont import FreeTypeFont, load_default as load_default_font, truetype as load_truetype

from folder_paths import get_folder_paths


# 修改了這行以反映新的資料夾名稱
default_font_path = Path(get_folder_paths("custom_nodes")[0]) / "ComfyUI-ImageLabel_extended" / "fonts"


class FontCollection(dict):
    """
    A dictionary that maps font names to PIL font objects.
    """

    def __init__(self, directory: Path = default_font_path):
        """
        Initialize the FontCollection with fonts found in the given directory (including subdirectories).

        Args:
            directory (Path): The path to the directory containing font files.
        """
        # 新增日誌以方便偵錯路徑問題
        logging.info(f"[FontCollection] Initializing FontCollection.")
        logging.info(f"[FontCollection] Attempting to load fonts from directory: {directory.resolve()}")

        if not directory.exists():
            logging.warning(f"[FontCollection] Font directory does not exist: {directory.resolve()}")
            paths = []
        else:
            paths = [font for font in directory.rglob("*.[tT][tT][fF]") if font.is_file()]
        
        logging.info(f"[FontCollection] Found font files: {paths}")

        try:
            self.default_font_name, self.default_font = self.load_default_font()
            fonts = {
                self.default_font_name: self.default_font,
            }
            logging.info(f"[FontCollection] Loaded default font: {self.default_font_name}")
        except Exception as e:
            logging.error(f"[FontCollection] Failed to load default font: {e}")
            # 如果預設字型也無法載入，則初始化一個空字典，並將 default_font_name 設為 None 或一個特殊值
            self.default_font_name = "Default_Font_Unavailable" 
            self.default_font = None # 或者嘗試使用一個絕對可靠的備用字型（如果Pillow有提供）
            fonts = {}


        for path in paths:
            try:
                font_info = self.load_font(path)
                if font_info:
                    if font_info[0] in fonts:
                        logging.warning(f"[FontCollection] Font with duplicate name found (will be overwritten): '{font_info[0]}' from path {path}")
                    fonts[font_info[0]] = font_info[1]
                    logging.info(f"[FontCollection] Loaded custom font: '{font_info[0]}' from {path.name}")
            except Exception as e:
                logging.error(f"[FontCollection] Failed to load font from {path}: {e}")
        
        super().__init__(fonts)
        logging.info(f"[FontCollection] Finished loading. Available fonts: {list(self.keys())}")

    @classmethod
    def load_default_font(cls) -> Tuple[str, FreeTypeFont]:
        """
        Load the default PIL font.

        Returns:
            tuple[str, FreeTypeFont]: The font's name and the font object.
        """
        font = load_default_font()
        # family, style = None, None # 移除，因為 getname() 會返回元組或 None
        if not isinstance(font, FreeTypeFont):
            # 理論上 load_default_font() 失敗會拋出 OSError，但多一層檢查總是好的
            raise RuntimeError("Could not load default FreeType font or it's not a FreeTypeFont instance.")
        
        name_tuple = font.getname()
        if name_tuple:
            family, style = name_tuple
        else: # getname() 可能返回 None
            family, style = "DefaultPillowFont", "Regular" # 提供一個備用名稱

        family = family or "UnknownDefaultFamily" # 確保 family 不是 None 或空字串
        style = style or "Regular" # 確保 style 不是 None 或空字串
        return " ".join([family, style]), font

    @classmethod
    def load_font(cls, path: Path) -> Tuple[str, FreeTypeFont]:
        """
        Load a font and extract its name and style.

        Args:
            path (Path): The path to the font file.

        Returns:
            tuple[str, ImageFont.FreeTypeFont]: A tuple containing the font's name and the font object.

        Raises:
            OSError: If the font file could not be read.
            ValueError: If the font size is not greater than zero. (Pillow's load_truetype 不會因 size=0 引發 ValueError，而是稍後使用時)
        """
        # load_truetype 的第二個參數是字體大小，但 FontCollection 通常只載入字體物件本身，大小在實際使用時指定。
        # 此處不需要指定 size，Pillow 會使用預設值或在後續 .font_variant(size=...) 時處理。
        font = load_truetype(str(path)) # Path 物件轉為字串以相容舊版 Pillow
        
        name_tuple = font.getname()
        if name_tuple:
            family, style = name_tuple
        else: # getname() 可能返回 None，這種情況較少見於正常的 TTF 檔案
             # 可以考慮從檔案名稱提取一個備用名稱
            family, style = path.stem, "UnknownStyle"

        family = family or path.stem # 如果字型內部名稱 family 為空，嘗試使用檔案名作為 family
        style = style or "Regular" # 確保 style 不是 None 或空字串
        
        # 避免 family 和 style 完全一樣導致重複名稱，例如 "Arial Arial"
        if family == style:
            return family, font # 只返回 family 名稱
        return " ".join([family, style]), font
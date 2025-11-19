from .advanced_text_filter import AdvancedTextFilter
from .text_input import TextInput
from .text_scraper import TextScraper
from .text_storage import TextStorage
from .wildcards import Wildcards, WildcardsAdv
from .add_text_to_image import AddTextToImage

NODE_CLASS_MAPPINGS = {
    "AdvancedTextFilter": AdvancedTextFilter,
    "TextInput": TextInput,
    "TextScraper": TextScraper,
    "TextStorage": TextStorage,
    "Wildcards": Wildcards,
    "WildcardsAdv": WildcardsAdv,
    "AddTextToImage": AddTextToImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AdvancedTextFilter": "Advanced Text Filter Node",
    "TextInput": "Text Input Node",
    "TextScraper": "Text Scraper Node",
    "TextStorage": "Text Storage Node",
    "Wildcards": "Wildcards Node",
    "WildcardsAdv": "Advanced Wildcards Node",
    "AddTextToImage": "Add text to image",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
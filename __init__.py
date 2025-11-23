from .advanced_text_filter import AdvancedTextFilter
from .text_input import TextInput
from .text_scraper import TextScraper
from .text_storage import TextStorage
from .wildcards import WildcardsNode
from .add_text_to_image import AddTextToImage
from .simple_eval import EvaluateInts, EvaluateFloats, EvaluateStrs

from .image_cropper import NODE_CLASS_MAPPINGS as IMAGE_CLASS_MAPPINGS
from .image_cropper import NODE_DISPLAY_NAME_MAPPINGS as IMAGE_DISPLAY_NAME_MAPPINGS

NODE_CLASS_MAPPINGS = {
    "AdvancedTextFilter": AdvancedTextFilter,
    "TextInput": TextInput,
    "TextScraper": TextScraper,
    "TextStorage": TextStorage,
    "WildcardsNode": WildcardsNode,
    "AddTextToImage": AddTextToImage,
    "EvaluateInts": EvaluateInts,
    "EvaluateFloats": EvaluateFloats,
    "EvaluateStrs": EvaluateStrs,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AdvancedTextFilter": "Advanced Text Filter",
    "TextInput": "Text Input",
    "TextScraper": "Text Scraper",
    "TextStorage": "Text Storage",
    "WildcardsNode": "Wildcards Processor",
    "AddTextToImage": "Add text to image",
    "EvaluateInts": "Simple Eval Integers",
    "EvaluateFloats": "Simple Eval Floats",
    "EvaluateStrs": "Simple Eval Strings",
}

NODE_CLASS_MAPPINGS.update(IMAGE_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(IMAGE_DISPLAY_NAME_MAPPINGS)

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
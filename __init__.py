from .advanced_text_filter import AdvancedTextFilter
from .text_input import TextInput
from .text_scraper import TextScraper
from .text_storage import NODE_CLASS_MAPPINGS as TEXT_STORAGE_CLASS_MAPPINGS
from .text_storage import NODE_DISPLAY_NAME_MAPPINGS as TEXT_STORAGE_NAME_MAPPINGS
from .wildcards import WildcardsNode
from .add_text_to_image import AddTextToImage
from .simple_eval import EvaluateInts, EvaluateFloats, EvaluateStrs

from .advanced_image_saver import AdvancedImageSaver

from .image_cropper import NODE_CLASS_MAPPINGS as IMAGE_CLASS_MAPPINGS
from .image_cropper import NODE_DISPLAY_NAME_MAPPINGS as IMAGE_DISPLAY_NAME_MAPPINGS

from .mask_nodes import NODE_CLASS_MAPPINGS as MASK_CLASS_MAPPINGS
from .mask_nodes import NODE_DISPLAY_NAME_MAPPINGS as MASK_DISPLAY_NAME_MAPPINGS

from .Image_concat_advanced import NODE_CLASS_MAPPINGS as CONCAT_CLASS_MAPPINGS
from .Image_concat_advanced import NODE_DISPLAY_NAME_MAPPINGS as CONCAT_DISPLAY_NAME_MAPPINGS

from .load_image_batch import NODE_CLASS_MAPPINGS as LOAD_IMAGE_BATCH_CLASS_MAPPINGS
from .load_image_batch import NODE_DISPLAY_NAME_MAPPINGS as LOAD_IMAGE_BATCH_DISPLAY_NAME_MAPPINGS

from .resize_image_advanced import NODE_CLASS_MAPPINGS as RESIZE_IMAGE_ADVANCED_CLASS_MAPPINGS
from .resize_image_advanced import NODE_DISPLAY_NAME_MAPPINGS as RESIZE_IMAGE_ADVANCED_DISPLAY_NAME_MAPPINGS
from .global_random_seed import NODE_CLASS_MAPPINGS as GLOBAL_RANDOM_SEED_CLASS_MAPPINGS
from .global_random_seed import NODE_DISPLAY_NAME_MAPPINGS as GLOBAL_RANDOM_SEED_DISPLAY_NAME_MAPPINGS
from .global_random_seed import register_available_prompt_server

NODE_CLASS_MAPPINGS = {
    "AdvancedTextFilter": AdvancedTextFilter,
    "TextInput": TextInput,
    "TextScraper": TextScraper,
    "WildcardsNode": WildcardsNode,
    "AddTextToImage": AddTextToImage,
    "EvaluateInts": EvaluateInts,
    "EvaluateFloats": EvaluateFloats,
    "EvaluateStrs": EvaluateStrs,
    "AdvancedImageSaver": AdvancedImageSaver,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AdvancedTextFilter": "Advanced Text Filter",
    "TextInput": "Text Input",
    "TextScraper": "Text Scraper",
    "WildcardsNode": "Wildcards Processor",
    "AddTextToImage": "Add text to image",
    "EvaluateInts": "Simple Eval Integers",
    "EvaluateFloats": "Simple Eval Floats",
    "EvaluateStrs": "Simple Eval Strings",
    "AdvancedImageSaver": "Advanced Image Saver (Aesthetic)",
}

NODE_CLASS_MAPPINGS.update(TEXT_STORAGE_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(TEXT_STORAGE_NAME_MAPPINGS)

NODE_CLASS_MAPPINGS.update(IMAGE_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(IMAGE_DISPLAY_NAME_MAPPINGS)

NODE_CLASS_MAPPINGS.update(MASK_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(MASK_DISPLAY_NAME_MAPPINGS)

NODE_CLASS_MAPPINGS.update(CONCAT_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(CONCAT_DISPLAY_NAME_MAPPINGS)

NODE_CLASS_MAPPINGS.update(LOAD_IMAGE_BATCH_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(LOAD_IMAGE_BATCH_DISPLAY_NAME_MAPPINGS)

NODE_CLASS_MAPPINGS.update(RESIZE_IMAGE_ADVANCED_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(RESIZE_IMAGE_ADVANCED_DISPLAY_NAME_MAPPINGS)

NODE_CLASS_MAPPINGS.update(GLOBAL_RANDOM_SEED_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(GLOBAL_RANDOM_SEED_DISPLAY_NAME_MAPPINGS)

register_available_prompt_server()

WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

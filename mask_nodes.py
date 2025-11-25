import os
import numpy as np
import torch
from PIL import Image, ImageOps
import folder_paths

class TP_SaveMask:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = ""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "mask": ("MASK", ),
                "filename_prefix": ("STRING", {"default": "Mask_Output"}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_mask"
    OUTPUT_NODE = True
    CATEGORY = "ComfyUI Text Processor/Image"

    def save_mask(self, mask, filename_prefix="Mask_Output"):
        full_output_folder, filename, counter, subfolder, filename_prefix = \
            folder_paths.get_save_image_path(filename_prefix, self.output_dir, mask.shape[2], mask.shape[1])
        
        results = list()
        for batch_number, single_mask in enumerate(mask):
            i = 255. * single_mask.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            
            file = f"{filename}_{counter:05}_.png"
            img.save(os.path.join(full_output_folder, file))
            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self.type
            })
            counter += 1
        
        return { "ui": { "images": results } }

class TP_LoadMask:
    @classmethod
    def INPUT_TYPES(s):
        files = folder_paths.get_filename_list("input")
        return {
            "required": {
                "image": (sorted(files), {"image_upload": True})
            },
        }

    CATEGORY = "ComfyUI Text Processor/Image"
    RETURN_TYPES = ("MASK", )
    FUNCTION = "load_mask"

    def load_mask(self, image):
        image_path = folder_paths.get_annotated_filepath(image)
        i = Image.open(image_path)
        i = ImageOps.exif_transpose(i)
        
        if i.mode != 'L':
            i = i.convert('L')
            
        image = np.array(i).astype(np.float32) / 255.0
        mask = torch.from_numpy(image)
        
        mask = mask.unsqueeze(0)
        
        return (mask, )

NODE_CLASS_MAPPINGS = {
    "TP_SaveMask": TP_SaveMask,
    "TP_LoadMask": TP_LoadMask
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TP_SaveMask": "Save Mask",
    "TP_LoadMask": "Load Mask"
}
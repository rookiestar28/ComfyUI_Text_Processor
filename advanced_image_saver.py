import os
import json
import re
import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from datetime import datetime
import folder_paths

class AdvancedImageSaver:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = 'output'
        self.prefix_append = ""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", ),
                "output_path": ("STRING", {"default": '[time(%Y-%m-%d)]', "multiline": False}),
                "filename_prefix": ("STRING", {"default": "ComfyUI"}),
                "filename_delimiter": ("STRING", {"default":"_"}),
                "filename_number_padding": ("INT", {"default":4, "min":1, "max":9, "step":1}),
                "filename_number_start": (["false", "true"],),
                "extension": (['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff'], ),
                "dpi": ("INT", {"default": 300, "min": 1, "max": 2400, "step": 1}),
                "quality": ("INT", {"default": 100, "min": 1, "max": 100, "step": 1}),
                "optimize_image": (["true", "false"],),
                "lossless_webp": (["false", "true"],),
                "overwrite_mode": (["false", "prefix_as_filename"],),
                "embed_workflow": (["true", "false"],),
                "show_previews": (["true", "false"],),
                "save_metadata": (["true", "false"],),
                "aesthetic_threshold": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 10.0, "step": 0.1}),
            },
            "optional": {
                "aesthetic_score": ("STRING", {"forceInput": True}),
            },
            "hidden": {
                "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING",)
    RETURN_NAMES = ("images", "files",)

    FUNCTION = "save_images"

    OUTPUT_NODE = True

    CATEGORY = "Text Processor/IO"

    def parse_name(self, text):
        """
        簡易的 Token 解析器，取代 WAS 的 TextTokens。
        目前支援 [time(format)] 語法。
        """
        if not text:
            return ""
            
        def replace_time(match):
            fmt = match.group(1)
            try:
                return datetime.now().strftime(fmt)
            except:
                return match.group(0)

        text = re.sub(r'\[time\((.*?)\)\]', replace_time, text)
        return text

    def save_images(self, images, output_path='', filename_prefix="ComfyUI", filename_delimiter='_',
                    extension='png', dpi=300, quality=100, optimize_image="true", lossless_webp="false", 
                    prompt=None, extra_pnginfo=None, overwrite_mode='false', filename_number_padding=4, 
                    filename_number_start='false', embed_workflow="true", show_previews="true", 
                    save_metadata="true", aesthetic_threshold=5.0, aesthetic_score=None):

        delimiter = filename_delimiter
        number_padding = filename_number_padding
        lossless_webp = (lossless_webp == "true")
        optimize_image = (optimize_image == "true")
        save_metadata_bool = (save_metadata == "true")
        embed_workflow_bool = (embed_workflow == "true")

        filename_prefix = self.parse_name(filename_prefix)
        output_path = self.parse_name(output_path)

        if output_path in [None, '', "none", "."]:
            full_output_folder = self.output_dir
        else:
            if os.path.isabs(output_path):
                full_output_folder = output_path
            else:
                full_output_folder = os.path.join(self.output_dir, output_path)
        
        if not os.path.exists(full_output_folder):
            try:
                os.makedirs(full_output_folder, exist_ok=True)
            except Exception as e:
                print(f"[AdvancedImageSaver] Error creating directory: {e}")
                full_output_folder = self.output_dir

        if filename_number_start == 'true':
            pattern = f"(\\d+){re.escape(delimiter)}{re.escape(filename_prefix)}"
        else:
            pattern = f"{re.escape(filename_prefix)}{re.escape(delimiter)}(\\d+)"

        existing_counters = []
        if os.path.exists(full_output_folder):
            for filename in os.listdir(full_output_folder):
                match = re.search(pattern, filename)
                if match:
                    try:
                        existing_counters.append(int(match.group(1)))
                    except ValueError:
                        pass
        
        existing_counters.sort(reverse=True)
        counter = existing_counters[0] + 1 if existing_counters else 1

        valid_extensions = ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff']
        if extension not in valid_extensions:
            print(f"[AdvancedImageSaver] Invalid extension: {extension}, defaulting to png")
            extension = 'png'
        file_extension = '.' + extension

        results = list()
        output_files = list()

        for idx, image in enumerate(images):
            
            if aesthetic_score is not None:
                try:
                    current_score_val = 0.0
                    if isinstance(aesthetic_score, list):
                        if idx < len(aesthetic_score):
                            current_score_val = float(aesthetic_score[idx])
                        else:
                            current_score_val = float(aesthetic_score[-1])
                    else:
                        current_score_val = float(aesthetic_score)
                    
                    if current_score_val < aesthetic_threshold:
                        print(f"[AdvancedImageSaver] Skipped image {idx} (Score: {current_score_val:.2f} < {aesthetic_threshold})")
                        continue 
                except (ValueError, TypeError):
                    print(f"[AdvancedImageSaver] Warning: Invalid aesthetic score input, skipping filter for image {idx}")
                    pass

            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            exif_data = None
            if save_metadata_bool:
                if extension == 'webp':
                    img_exif = img.getexif()
                    workflow_metadata = ''
                    prompt_str = ''
                    if prompt is not None:
                        prompt_str = json.dumps(prompt)
                        img_exif[0x010f] = "Prompt:" + prompt_str
                    if embed_workflow_bool and extra_pnginfo is not None:
                        for x in extra_pnginfo:
                            workflow_metadata += json.dumps(extra_pnginfo[x])
                        img_exif[0x010e] = "Workflow:" + workflow_metadata
                    exif_data = img_exif.tobytes()
                else:
                    metadata = PngInfo()
                    if prompt is not None:
                        metadata.add_text("prompt", json.dumps(prompt))
                    if embed_workflow_bool and extra_pnginfo is not None:
                        for x in extra_pnginfo:
                            metadata.add_text(x, json.dumps(extra_pnginfo[x]))
                    exif_data = metadata

            if overwrite_mode == 'prefix_as_filename':
                file_name = f"{filename_prefix}{file_extension}"
            else:
                if filename_number_start == 'true':
                    file_name = f"{counter:0{number_padding}}{delimiter}{filename_prefix}{file_extension}"
                else:
                    file_name = f"{filename_prefix}{delimiter}{counter:0{number_padding}}{file_extension}"
                
                while os.path.exists(os.path.join(full_output_folder, file_name)):
                    counter += 1
                    if filename_number_start == 'true':
                        file_name = f"{counter:0{number_padding}}{delimiter}{filename_prefix}{file_extension}"
                    else:
                        file_name = f"{filename_prefix}{delimiter}{counter:0{number_padding}}{file_extension}"

            try:
                full_file_path = os.path.join(full_output_folder, file_name)
                
                if extension in ["jpg", "jpeg"]:
                    img.save(full_file_path, quality=quality, optimize=optimize_image, dpi=(dpi, dpi))
                elif extension == 'webp':
                    img.save(full_file_path, quality=quality, lossless=lossless_webp, exif=exif_data)
                elif extension == 'png':
                    img.save(full_file_path, pnginfo=exif_data, optimize=optimize_image, dpi=(dpi, dpi))
                elif extension == 'bmp':
                    img.save(full_file_path)
                elif extension == 'tiff':
                    img.save(full_file_path, quality=quality, optimize=optimize_image)
                else:
                    img.save(full_file_path, pnginfo=exif_data, optimize=optimize_image)

                print(f"[AdvancedImageSaver] Saved: {full_file_path}")
                output_files.append(full_file_path)

                if show_previews == 'true':
                    subfolder = os.path.relpath(full_output_folder, self.output_dir)
                    if subfolder == '.': 
                        subfolder = ""
                        
                    results.append({
                        "filename": file_name,
                        "subfolder": subfolder,
                        "type": self.type
                    })

            except OSError as e:
                print(f"[AdvancedImageSaver] OSError: Unable to save file to {full_file_path}: {e}")
            except Exception as e:
                print(f"[AdvancedImageSaver] Error: {e}")

            if overwrite_mode == 'false':
                counter += 1

        if show_previews == 'true':
            return {"ui": {"images": results, "files": output_files}, "result": (images, output_files,)}
        else:
            return {"ui": {"images": []}, "result": (images, output_files,)}
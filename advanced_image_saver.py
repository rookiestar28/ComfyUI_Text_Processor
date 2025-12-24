import os
import json
import re
import numpy as np
import torch
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from datetime import datetime
import folder_paths

try:
    from aesthetic_predictor_v2_5 import convert_v2_5_from_siglip
except ImportError:
    print("[AdvancedImageSaver] Warning: aesthetic_predictor_v2_5 module not found. Aesthetic scoring will fail if enabled.")

class AdvancedImageSaver:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = 'output'
        self.prefix_append = ""
        
        self.predictor_model = None
        self.predictor_preprocessor = None

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
                "calculate_aesthetic_score": (["false", "true"],),
                "aesthetic_threshold": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 10.0, "step": 0.1}),
            },
            "optional": {
                "aesthetic_score": ("STRING", {"forceInput": True}),
            },
            "hidden": {
                "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING",)
    RETURN_NAMES = ("filtered_images", "files", "scores",)

    FUNCTION = "save_images"

    OUTPUT_NODE = True

    CATEGORY = "Text Processor/IO"

    def parse_name(self, text):
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

    def load_predictor(self):
        """加載評分模型，如果尚未加載"""
        if self.predictor_model is not None:
            return

        print("[AdvancedImageSaver] Loading Aesthetic Predictor V2.5 model...")
        try:
            self.predictor_model, self.predictor_preprocessor = convert_v2_5_from_siglip(
                low_cpu_mem_usage=True,
                trust_remote_code=True,
            )
            if torch.cuda.is_available():
                self.predictor_model = self.predictor_model.to(torch.bfloat16).cuda()
            print("[AdvancedImageSaver] Model loaded successfully.")
        except Exception as e:
            print(f"[AdvancedImageSaver] Error loading model: {e}")
            raise e

    def get_aesthetic_score(self, image_tensor):
        """計算單張圖片的美學分數"""
        try:
            # Convert to numpy, scale to 255, uint8
            img_np = (image_tensor.cpu().numpy() * 255).astype(np.uint8)
            image = Image.fromarray(img_np).convert("RGB")
            
            # Preprocess
            pixel_values = self.predictor_preprocessor(images=image, return_tensors="pt").pixel_values

            if torch.cuda.is_available():
                pixel_values = pixel_values.to(torch.bfloat16).cuda()

            # Predict
            with torch.inference_mode():
                score = self.predictor_model(pixel_values).logits.squeeze().float().cpu().numpy()
            
            return float(score)
        except Exception as e:
            print(f"[AdvancedImageSaver] Prediction failed: {e}")
            return 0.0

    def save_images(self, images, output_path='', filename_prefix="ComfyUI", filename_delimiter='_',
                    extension='png', dpi=300, quality=100, optimize_image="true", lossless_webp="false", 
                    prompt=None, extra_pnginfo=None, overwrite_mode='false', filename_number_padding=4, 
                    filename_number_start='false', embed_workflow="true", show_previews="true", 
                    save_metadata="true", calculate_aesthetic_score="false", aesthetic_threshold=5.0, aesthetic_score=None):

        delimiter = filename_delimiter
        number_padding = filename_number_padding
        lossless_webp = (lossless_webp == "true")
        optimize_image = (optimize_image == "true")
        save_metadata_bool = (save_metadata == "true")
        embed_workflow_bool = (embed_workflow == "true")
        calculate_score_bool = (calculate_aesthetic_score == "true")

        if calculate_score_bool:
            self.load_predictor()

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
        saved_scores = list()
        valid_images_list = list() 

        for idx, image in enumerate(images):
            
            should_save = True
            current_score_val = None

            if calculate_score_bool and self.predictor_model is not None:
                current_score_val = self.get_aesthetic_score(image)
                print(f"[AdvancedImageSaver] Image {idx} Score: {current_score_val:.4f}")

            elif aesthetic_score is not None:
                try:
                    if isinstance(aesthetic_score, list):
                        if idx < len(aesthetic_score):
                            current_score_val = float(aesthetic_score[idx])
                        else:
                            current_score_val = float(aesthetic_score[-1])
                    else:
                        current_score_val = float(aesthetic_score)
                except (ValueError, TypeError):
                    pass
            
            if current_score_val is not None:
                if current_score_val < aesthetic_threshold:
                    continue 
            
            valid_images_list.append(image)
            if current_score_val is not None:
                saved_scores.append(f"{current_score_val:.4f}")
            else:
                saved_scores.append("N/A")

            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            exif_data = None
            if save_metadata_bool:
                items_to_save = {}
                
                if prompt is not None:
                    items_to_save["prompt"] = json.dumps(prompt)

                if extra_pnginfo is not None:
                    for key, value in extra_pnginfo.items():
                        if key == 'workflow' and not embed_workflow_bool:
                            continue
                        items_to_save[key] = json.dumps(value)

                if extension == 'webp':
                    img_exif = img.getexif()
                    if "prompt" in items_to_save:
                        img_exif[0x010f] = "Prompt:" + items_to_save["prompt"]
                    
                    workflow_metadata = ""
                    for key, value in items_to_save.items():
                        if key == "prompt": continue
                        workflow_metadata += value
                    
                    if workflow_metadata:
                        img_exif[0x010e] = "Workflow:" + workflow_metadata
                        
                    exif_data = img_exif.tobytes()
                else:
                    # PNG
                    metadata = PngInfo()
                    for key, value in items_to_save.items():
                        metadata.add_text(key, value)
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
                    if subfolder == '.': subfolder = ""
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
        
        if len(valid_images_list) > 0:
            filtered_images_out = torch.stack(valid_images_list)
        else:

            filtered_images_out = torch.empty((0, 1, 1, 3))

        if show_previews == 'true':
            return {"ui": {"images": results, "files": output_files}, "result": (filtered_images_out, output_files, saved_scores)}
        else:
            return {"ui": {"images": []}, "result": (filtered_images_out, output_files, saved_scores)}
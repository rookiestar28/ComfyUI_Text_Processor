import numpy as np
import torch
import torchvision.transforms.functional as F
from PIL import Image, ImageFilter
from torchvision.transforms import InterpolationMode

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

def register_node(identifier: str, display_name: str):
    def decorator(cls):
        NODE_CLASS_MAPPINGS[identifier] = cls
        NODE_DISPLAY_NAME_MAPPINGS[identifier] = display_name
        return cls
    return decorator


def tensor2pil(image: torch.Tensor) -> Image.Image:
    return Image.fromarray(np.clip(255. * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

def pil2tensor(image: Image.Image) -> torch.Tensor:
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)

def get_mask_center(mask: Image.Image):
    """計算 Mask 的重心座標 (x, y)"""
    mask = mask.convert("L")
    mask = mask.filter(ImageFilter.GaussianBlur(radius=5))
    bbox = mask.getbbox()
    if bbox:
        return (bbox[0] + (bbox[2] - bbox[0]) // 2, bbox[1] + (bbox[3] - bbox[1]) // 2)
    return (mask.width // 2, mask.height // 2)

@register_node("ImageCropper", "Image Cropper")
class _:
    CATEGORY = "ComfyUI_Text_Processor/Image"
    INPUT_TYPES = lambda: {
        "required": {
            "image": ("IMAGE",),
            
            "enable_fixed_crop": ("BOOLEAN", {"default": False}),
            
            "fixed_crop_side": (["shortest", "longest", "width", "height"],),
            "fixed_crop_length": ("INT", {"default": 512, "min": 1, "max": 99999, "step": 1}),
            
            "aspect_ratio": (["1:1", "3:2", "4:3", "16:9", "2:3", "3:4", "9:16", "custom", "original"],),
            "proportional_width": ("INT", {"default": 1, "min": 1, "max": 999999, "step": 1}),
            "proportional_height": ("INT", {"default": 1, "min": 1, "max": 999999, "step": 1}),
            
            "alignment": (["center", "top-left", "top-right", "bottom-left", "bottom-right"],),
            "offset_x": ("INT", {"default": 0, "min": -99999, "max": 99999, "step": 1}),
            "offset_y": ("INT", {"default": 0, "min": -99999, "max": 99999, "step": 1}),
            
            "scale_to_side": (["None", "longest", "shortest", "width", "height"],),
            "scale_to_length": ("INT", {"default": 1024, "min": 1, "max": 999999, "step": 1}),
            "interpolation_mode": (["bicubic", "bilinear", "nearest", "nearest exact"],),
        },
        "optional": {
            "mask": ("MASK",),
        }
    }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    def execute(self, image, enable_fixed_crop, fixed_crop_side, fixed_crop_length,
                aspect_ratio, proportional_width, proportional_height,
                alignment, offset_x, offset_y,
                scale_to_side, scale_to_length, interpolation_mode, mask=None):
        
        interp_mode = interpolation_mode.upper().replace(" ", "_")
        interp_mode = getattr(InterpolationMode, interp_mode)

        ret_images = []
        
        if mask is not None:
            if mask.dim() == 2: mask = mask.unsqueeze(0)
            if mask.shape[0] == 1 and len(image) > 1: mask = mask.repeat(len(image), 1, 1)
        
        for i in range(len(image)):
            source_img_pil = tensor2pil(image[i])
            orig_w, orig_h = source_img_pil.size

            crop_target_w = orig_w
            crop_target_h = orig_h

            if enable_fixed_crop:
                if fixed_crop_side == 'width':
                    crop_target_w = fixed_crop_length
                elif fixed_crop_side == 'height':
                    crop_target_h = fixed_crop_length
                elif fixed_crop_side == 'shortest':
                    if orig_w <= orig_h: crop_target_w = fixed_crop_length
                    else:                crop_target_h = fixed_crop_length
                elif fixed_crop_side == 'longest':
                    if orig_w >= orig_h: crop_target_w = fixed_crop_length
                    else:                crop_target_h = fixed_crop_length
            else:
                if aspect_ratio == 'custom':
                    ratio = proportional_width / proportional_height
                elif aspect_ratio == 'original':
                    ratio = orig_w / orig_h
                else:
                    s = aspect_ratio.split(":")
                    ratio = int(s[0]) / int(s[1])
                
                orig_ratio = orig_w / orig_h
                if orig_ratio > ratio: 
                    crop_target_h = orig_h
                    crop_target_w = int(orig_h * ratio)
                else: 
                    crop_target_w = orig_w
                    crop_target_h = int(orig_w / ratio)

            crop_target_w = min(crop_target_w, orig_w)
            crop_target_h = min(crop_target_h, orig_h)

            if mask is not None and i < len(mask):
                mask_pil = Image.fromarray((mask[i].cpu().numpy() * 255).astype(np.uint8), mode='L')
                center_x, center_y = get_mask_center(mask_pil)
            else:
                center_x, center_y = orig_w // 2, orig_h // 2

            if alignment == 'top-left':
                base_x, base_y = 0 + crop_target_w // 2, 0 + crop_target_h // 2
            elif alignment == 'top-right':
                base_x, base_y = orig_w - crop_target_w // 2, 0 + crop_target_h // 2
            elif alignment == 'bottom-left':
                base_x, base_y = 0 + crop_target_w // 2, orig_h - crop_target_h // 2
            elif alignment == 'bottom-right':
                base_x, base_y = orig_w - crop_target_w // 2, orig_h - crop_target_h // 2
            else: # center
                base_x, base_y = center_x, center_y

            final_center_x = base_x + offset_x
            final_center_y = base_y + offset_y

            crop_x = final_center_x - crop_target_w // 2
            crop_y = final_center_y - crop_target_h // 2

            if crop_x < 0: crop_x = 0
            if crop_y < 0: crop_y = 0
            if crop_x + crop_target_w > orig_w: crop_x = orig_w - crop_target_w
            if crop_y + crop_target_h > orig_h: crop_y = orig_h - crop_target_h

            cropped_img = source_img_pil.crop((crop_x, crop_y, crop_x + crop_target_w, crop_y + crop_target_h))

            final_img = cropped_img
            if scale_to_side != 'None':
                current_w, current_h = final_img.size
                resize_w, resize_h = current_w, current_h
                current_ratio = current_w / current_h

                if scale_to_side == 'width':
                    resize_w = scale_to_length
                    resize_h = int(resize_w / current_ratio)
                elif scale_to_side == 'height':
                    resize_h = scale_to_length
                    resize_w = int(resize_h * current_ratio)
                elif scale_to_side == 'longest':
                    if current_w >= current_h:
                        resize_w = scale_to_length
                        resize_h = int(resize_w / current_ratio)
                    else:
                        resize_h = scale_to_length
                        resize_w = int(resize_h * current_ratio)
                elif scale_to_side == 'shortest':
                    if current_w <= current_h:
                        resize_w = scale_to_length
                        resize_h = int(resize_w / current_ratio)
                    else:
                        resize_h = scale_to_length
                        resize_w = int(resize_h * current_ratio)

                tensor_crop = pil2tensor(final_img)
                tensor_crop = tensor_crop.permute(0, 3, 1, 2)
                tensor_resized = F.resize(
                    tensor_crop, 
                    [resize_h, resize_w], 
                    interpolation=interp_mode, 
                    antialias=True
                )
                tensor_resized = tensor_resized.permute(0, 2, 3, 1)
                ret_images.append(tensor_resized)
            else:
                ret_images.append(pil2tensor(final_img))

        if len(ret_images) > 1:
             return (torch.cat(ret_images, dim=0),)
        return (ret_images[0],)
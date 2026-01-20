import logging
import textwrap
from typing import Tuple, List, Optional

import torch
from torch import Tensor
from torchvision.transforms.v2.functional import to_pil_image, to_image
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont
from .font_manager import FontCollection

logger = logging.getLogger(__name__)


class AddTextToImage:
    fonts = FontCollection()

    def _parse_color_with_alpha(self, color_hex: str, default_alpha: int = 255) -> Tuple[int, int, int, int]:
        color_hex = color_hex.lstrip('#')
        if len(color_hex) == 6:
            r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
            return r, g, b, default_alpha
        elif len(color_hex) == 8:
            r, g, b, a = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4, 6))
            return r, g, b, a
        else:
            logger.warning(f"Invalid color format: '{color_hex}'. Using black opaque as fallback.")
            return 0, 0, 0, 255

    @staticmethod
    def _calculate_anchor_offset(
        anchor: str,
        text_width: float,
        text_height: float,
        base_x: float,
        base_y: float
    ) -> Tuple[float, float]:
        """
        Calculate the actual draw position based on anchor.
        Anchor format: [horizontal][vertical] e.g. 'lt', 'ms', 'mm'
        Horizontal: l=left, m=middle, r=right
        Vertical: t=top, m=middle, s=baseline, d=descender
        """
        draw_x, draw_y = base_x, base_y
        if len(anchor) >= 1:
            h_anchor = anchor[0]
            if h_anchor == 'm':
                draw_x -= text_width / 2
            elif h_anchor == 'r':
                draw_x -= text_width
        if len(anchor) >= 2:
            v_anchor = anchor[1]
            if v_anchor == 'm':
                draw_y -= text_height / 2
            elif v_anchor in ('s', 'd'):
                draw_y -= text_height
        return draw_x, draw_y

    def _wrap_text_to_width(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: FreeTypeFont,
        max_width: int,
        line_spacing: int
    ) -> str:
        """
        Wrap text to fit within max_width by inserting line breaks.
        Uses character-by-character measurement for accuracy with CJK characters.
        """
        if not text:
            return text
        
        lines = text.split('\n')
        wrapped_lines = []
        
        for line in lines:
            if not line:
                wrapped_lines.append('')
                continue
            
            # Measure line width
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
            except (TypeError, ValueError):
                line_width = len(line) * font.size  # Rough estimate
            
            if line_width <= max_width:
                wrapped_lines.append(line)
                continue
            
            # Need to wrap - use character-by-character approach for CJK support
            current_line = ""
            for char in line:
                test_line = current_line + char
                try:
                    bbox = draw.textbbox((0, 0), test_line, font=font)
                    test_width = bbox[2] - bbox[0]
                except (TypeError, ValueError):
                    test_width = len(test_line) * font.size
                
                if test_width <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        wrapped_lines.append(current_line)
                    current_line = char
            
            if current_line:
                wrapped_lines.append(current_line)
        
        return '\n'.join(wrapped_lines)

    def _truncate_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: FreeTypeFont,
        max_width: int,
        ellipsis: str = "..."
    ) -> str:
        """
        Truncate text to fit within max_width, adding ellipsis if truncated.
        Processes each line independently.
        """
        if not text:
            return text
        
        lines = text.split('\n')
        truncated_lines = []
        
        for line in lines:
            if not line:
                truncated_lines.append('')
                continue
            
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
            except (TypeError, ValueError):
                line_width = len(line) * font.size
            
            if line_width <= max_width:
                truncated_lines.append(line)
                continue
            
            # Need to truncate
            try:
                ellipsis_bbox = draw.textbbox((0, 0), ellipsis, font=font)
                ellipsis_width = ellipsis_bbox[2] - ellipsis_bbox[0]
            except (TypeError, ValueError):
                ellipsis_width = len(ellipsis) * font.size
            
            available_width = max_width - ellipsis_width
            if available_width <= 0:
                truncated_lines.append(ellipsis[:1])  # Just show first char of ellipsis
                continue
            
            # Find truncation point
            truncated = ""
            for char in line:
                test_text = truncated + char
                try:
                    bbox = draw.textbbox((0, 0), test_text, font=font)
                    test_width = bbox[2] - bbox[0]
                except (TypeError, ValueError):
                    test_width = len(test_text) * font.size
                
                if test_width <= available_width:
                    truncated = test_text
                else:
                    break
            
            truncated_lines.append(truncated + ellipsis)
        
        return '\n'.join(truncated_lines)

    def _find_optimal_font_size_with_height(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        base_font: FreeTypeFont,
        max_width: int,
        max_height: int,
        initial_size: int,
        min_size: int,
        line_spacing: int,
        auto_wrap: bool = False
    ) -> Tuple[FreeTypeFont, str, Tuple[int, int, int, int]]:
        """
        Find optimal font size that fits within both max_width and max_height.
        If auto_wrap is True, text will be wrapped before checking dimensions.
        Returns: (sized_font, processed_text, text_bbox)
        """
        low, high = min_size, initial_size
        best_font = base_font.font_variant(size=min_size)
        best_text = text
        best_bbox = (0, 0, 0, 0)

        while low <= high:
            mid = (low + high) // 2
            sized_font = base_font.font_variant(size=mid)
            
            # Apply word wrap if enabled
            if auto_wrap:
                processed_text = self._wrap_text_to_width(draw, text, sized_font, max_width, line_spacing)
            else:
                processed_text = text
            
            try:
                text_bbox = draw.multiline_textbbox(
                    (0, 0), processed_text, font=sized_font, spacing=line_spacing, align="center"
                )
            except (TypeError, ValueError):
                text_bbox = draw.multiline_textbbox(
                    (0, 0), processed_text, font=sized_font, spacing=line_spacing
                )
            
            actual_text_width = text_bbox[2] - text_bbox[0]
            actual_text_height = text_bbox[3] - text_bbox[1]

            # Check both width and height constraints
            fits_width = actual_text_width <= max_width
            fits_height = actual_text_height <= max_height

            if fits_width and fits_height:
                best_font = sized_font
                best_text = processed_text
                best_bbox = text_bbox
                low = mid + 1
            else:
                high = mid - 1

        return best_font, best_text, best_bbox

    @classmethod
    def INPUT_TYPES(cls):
        font_names = list(cls.fonts.keys())
        default_font_for_ui = ""
        if hasattr(cls.fonts, 'default_font_name') and cls.fonts.default_font_name and cls.fonts.default_font_name in font_names:
            default_font_for_ui = cls.fonts.default_font_name
        elif font_names:
            default_font_for_ui = font_names[0]
        else:
            font_names.append("No fonts available")
            default_font_for_ui = "No fonts available"

        return {
            "required": {
                "image": ("IMAGE",),
                "font_name": (font_names, {"default": default_font_for_ui}),
                "text_position": (["bottom_center", "top_center", "bottom_left", "bottom_right", "top_left", "top_right", "center_center"], {"default": "bottom_center"}),
                
                "background_mode": (["text_box", "full_width_strip"], {"default": "text_box"}),

                "font_size": ("INT", {"default": 48, "min": 4, "max": 1024, "step": 1}),
                "margin": ("INT", {"default": 24, "min": 0, "max": 256, "step": 1}),
                "line_spacing": ("INT", {"default": 5, "min": 0, "max": 128, "step": 1}),
                "text_color_hex": ("STRING", {"default": "#ffffff"}),
                "background_color_hex": ("STRING", {"default": "#00000080"}),
                "background_padding": ("INT", {"default": 10, "min": 0, "max": 50, "step": 1}),
                
                # New text adaptation options
                "auto_adapt": ("BOOLEAN", {"default": True, "label_on": "Auto Wrap + Shrink", "label_off": "Truncate"}),
                "min_font_size": ("INT", {"default": 8, "min": 4, "max": 128, "step": 1, "tooltip": "Minimum font size when auto_adapt is enabled"}),
            },
            "optional": {
                "label_text": ("STRING", {"multiline": True, "default": "Label 1\nLabel 2", "forceInput": False}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "execute_draw_on_batch"
    CATEGORY = "ComfyUI Text Processor/Image"

    def execute_draw_on_batch(
        self,
        image: Tensor,
        font_name: str,
        text_position: str,
        background_mode: str,
        font_size: int,
        margin: int,
        line_spacing: int,
        text_color_hex: str,
        background_color_hex: str,
        background_padding: int,
        auto_adapt: bool = True,
        min_font_size: int = 8,
        label_text: str = None,
    ):
        logger.debug("EXECUTE_DRAW_ON_BATCH START")
        
        if not isinstance(image, torch.Tensor) or image.ndim != 4:
            logger.error("Input image is not a valid batch tensor.")
            bs = image.shape[0] if isinstance(image, torch.Tensor) and image.ndim == 4 else 1
            return (torch.zeros((bs, 64, 64, 3), dtype=image.dtype if isinstance(image, torch.Tensor) else torch.float32, device=image.device if isinstance(image, torch.Tensor) else 'cpu'),)

        # Handle None or empty label_text gracefully
        if label_text is None or (isinstance(label_text, str) and not label_text.strip()):
            logger.warning("label_text is empty or None. Returning original image without text overlay.")
            return (image,)

        label_lines = [line.strip() for line in label_text.strip().split('\n') if line.strip()]
        if not label_lines:
            logger.warning("label_text contains no valid lines. Returning original image without text overlay.")
            return (image,)

        num_provided_labels = len(label_lines)
        batch_size = image.shape[0]
        processed_pil_images_chw: List[Tensor] = []

        try:
            base_font_object = self.fonts[font_name]
        except KeyError:
            logger.warning(f"Font '{font_name}' not found in FontCollection. Returning original image.")
            return (image,) 

        parsed_text_color = self._parse_color_with_alpha(text_color_hex, 255)
        parsed_bg_color_tuple = self._parse_color_with_alpha(background_color_hex, 128)
        logger.debug(f"Parsed background_color_hex '{background_color_hex}' to RGBA: {parsed_bg_color_tuple}")

        # Use user-defined min_font_size only when auto_adapt is enabled
        effective_min_font_size = min_font_size if auto_adapt else 8

        for i in range(batch_size):
            current_image_tensor_hwc = image[i]
            
            base_pil_image = to_pil_image(current_image_tensor_hwc.permute(2, 0, 1)).convert("RGBA")
            img_width, img_height = base_pil_image.size
            
            current_label_text = label_lines[i % num_provided_labels] if num_provided_labels > 0 else ""
            logger.debug(f"Processing image {i} (Size: {img_width}x{img_height}) with label: '{current_label_text}'")

            overlay_pil_image = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
            draw_on_overlay = ImageDraw.Draw(overlay_pil_image)
            
            sized_font: FreeTypeFont | None = None
            display_text = current_label_text

            if current_label_text:
                max_text_width = img_width - margin * 2
                max_text_height = img_height - margin * 2  # Height constraint

                if auto_adapt:
                    # Auto-adapt mode: wrap text and shrink font to fit
                    sized_font, display_text, text_bbox = self._find_optimal_font_size_with_height(
                        draw=draw_on_overlay,
                        text=current_label_text,
                        base_font=base_font_object,
                        max_width=max_text_width,
                        max_height=max_text_height,
                        initial_size=font_size,
                        min_size=effective_min_font_size,
                        line_spacing=line_spacing,
                        auto_wrap=True
                    )
                    logger.debug(f"Auto-adapt: font size optimized, text wrapped to {display_text.count(chr(10)) + 1} lines")
                else:
                    # Truncate mode: use fixed font size with truncation
                    sized_font = base_font_object.font_variant(size=font_size)
                    display_text = self._truncate_text(
                        draw=draw_on_overlay,
                        text=current_label_text,
                        font=sized_font,
                        max_width=max_text_width
                    )
                    try:
                        text_bbox = draw_on_overlay.multiline_textbbox(
                            (0, 0), display_text, font=sized_font, spacing=line_spacing, align="center"
                        )
                    except (TypeError, ValueError):
                        text_bbox = draw_on_overlay.multiline_textbbox(
                            (0, 0), display_text, font=sized_font, spacing=line_spacing
                        )
                    
                    # Check height and warn if text exceeds
                    text_height = text_bbox[3] - text_bbox[1]
                    if text_height > max_text_height:
                        logger.warning(f"Text height ({text_height}px) exceeds available height ({max_text_height}px). Text may be clipped.")
                
                text_draw_x, text_draw_y = 0.0, 0.0
                final_anchor = "lt"
                
                if text_position == "bottom_center": text_draw_x, text_draw_y, final_anchor = img_width / 2, float(img_height - margin), "ms"
                elif text_position == "top_center": text_draw_x, text_draw_y, final_anchor = img_width / 2, float(margin), "mt"
                elif text_position == "bottom_left": text_draw_x, text_draw_y, final_anchor = float(margin), float(img_height - margin), "ls"
                elif text_position == "bottom_right": text_draw_x, text_draw_y, final_anchor = float(img_width - margin), float(img_height - margin), "rs"
                elif text_position == "top_left": text_draw_x, text_draw_y, final_anchor = float(margin), float(margin), "lt"
                elif text_position == "top_right": text_draw_x, text_draw_y, final_anchor = float(img_width - margin), float(margin), "rt"
                elif text_position == "center_center": text_draw_x, text_draw_y, final_anchor = img_width / 2, img_height / 2, "mm"

                # Auto-adjust position to prevent text from being clipped when auto_adapt is enabled
                if auto_adapt and sized_font:
                    # Calculate actual text bounding box at the anchor position
                    try:
                        test_bbox = draw_on_overlay.multiline_textbbox(
                            (text_draw_x, text_draw_y), display_text, font=sized_font, 
                            spacing=line_spacing, align="center", anchor=final_anchor
                        )
                    except (TypeError, ValueError):
                        temp_bbox = draw_on_overlay.multiline_textbbox(
                            (0, 0), display_text, font=sized_font, spacing=line_spacing, align="center"
                        )
                        temp_w = temp_bbox[2] - temp_bbox[0]
                        temp_h = temp_bbox[3] - temp_bbox[1]
                        temp_x, temp_y = self._calculate_anchor_offset(
                            final_anchor, temp_w, temp_h, text_draw_x, text_draw_y
                        )
                        test_bbox = (temp_x, temp_y, temp_x + temp_w, temp_y + temp_h)
                    
                    # Check if text extends beyond image boundaries (with background padding)
                    text_y1 = test_bbox[1] - background_padding
                    text_y2 = test_bbox[3] + background_padding
                    text_x1 = test_bbox[0] - background_padding
                    text_x2 = test_bbox[2] + background_padding
                    
                    # Adjust Y position if text overflows vertically
                    if text_y2 > img_height:
                        overflow = text_y2 - img_height
                        text_draw_y -= overflow
                        logger.debug(f"Adjusted text Y position by -{overflow}px to prevent bottom overflow")
                    elif text_y1 < 0:
                        overflow = -text_y1
                        text_draw_y += overflow
                        logger.debug(f"Adjusted text Y position by +{overflow}px to prevent top overflow")
                    
                    # Adjust X position if text overflows horizontally (for non-center positions)
                    if background_mode != "full_width_strip":
                        if text_x2 > img_width:
                            overflow = text_x2 - img_width
                            text_draw_x -= overflow
                            logger.debug(f"Adjusted text X position by -{overflow}px to prevent right overflow")
                        elif text_x1 < 0:
                            overflow = -text_x1
                            text_draw_x += overflow
                            logger.debug(f"Adjusted text X position by +{overflow}px to prevent left overflow")


                if background_color_hex.lower() != "none" and parsed_bg_color_tuple[3] > 0 and sized_font:
                    bg_r, bg_g, bg_b, bg_a = parsed_bg_color_tuple
                    
                    try:
                        final_text_pixel_bbox = draw_on_overlay.multiline_textbbox((text_draw_x, text_draw_y), display_text, font=sized_font, spacing=line_spacing, align="center", anchor=final_anchor)
                    except (TypeError, ValueError): 
                        temp_text_bbox_for_fallback = draw_on_overlay.multiline_textbbox((0,0), display_text, font=sized_font, spacing=line_spacing, align="center")
                        fb_actual_text_width = temp_text_bbox_for_fallback[2] - temp_text_bbox_for_fallback[0]
                        fb_actual_text_height = temp_text_bbox_for_fallback[3] - temp_text_bbox_for_fallback[1]
                        fb_x1, fb_y1 = self._calculate_anchor_offset(
                            final_anchor, fb_actual_text_width, fb_actual_text_height, text_draw_x, text_draw_y
                        )
                        final_text_pixel_bbox = (fb_x1, fb_y1, fb_x1 + fb_actual_text_width, fb_y1 + fb_actual_text_height)

                    bg_x1 = final_text_pixel_bbox[0] - background_padding
                    bg_y1 = final_text_pixel_bbox[1] - background_padding
                    bg_x2 = final_text_pixel_bbox[2] + background_padding
                    bg_y2 = final_text_pixel_bbox[3] + background_padding
                    
                    if background_mode == "full_width_strip":
                        bg_x1 = 0
                        bg_x2 = float(img_width)
                    bg_y1 = max(0.0, bg_y1)
                    bg_y2 = min(float(img_height), bg_y2)
                    
                    if bg_y1 < bg_y2: 
                         if background_mode == "full_width_strip" or (bg_x1 < bg_x2):
                            draw_on_overlay.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill=(bg_r, bg_g, bg_b, bg_a))
                
                if sized_font:
                    try:
                        draw_on_overlay.multiline_text(xy=(text_draw_x, text_draw_y), text=display_text, fill=parsed_text_color, font=sized_font, anchor=final_anchor, spacing=line_spacing, align="center")
                    except (TypeError, ValueError):
                        # Fallback for Pillow versions that do not support anchor in multiline_text
                        temp_text_bbox = draw_on_overlay.multiline_textbbox((0,0), display_text, font=sized_font, spacing=line_spacing, align="center")
                        actual_w = temp_text_bbox[2] - temp_text_bbox[0]
                        actual_h = temp_text_bbox[3] - temp_text_bbox[1]
                        
                        draw_x, draw_y = self._calculate_anchor_offset(
                            final_anchor, actual_w, actual_h, text_draw_x, text_draw_y
                        )
                        
                        draw_on_overlay.multiline_text(xy=(draw_x, draw_y), text=display_text, fill=parsed_text_color, font=sized_font, spacing=line_spacing, align="center")

            final_pil_image_rgba = Image.alpha_composite(base_pil_image, overlay_pil_image)
            
            final_pil_image_rgb = final_pil_image_rgba.convert("RGB")
            
            output_tensor_chw = to_image(final_pil_image_rgb) / 255.0
            processed_pil_images_chw.append(output_tensor_chw)
        
        try:
            stacked_images_bchw = torch.stack(processed_pil_images_chw, dim=0)
            final_output_tensor_bhwc = stacked_images_bchw.permute(0, 2, 3, 1)
            logger.debug(f"Batch processed successfully. Output shape: {final_output_tensor_bhwc.shape}")
            logger.debug("EXECUTE_DRAW_ON_BATCH END")
            return (final_output_tensor_bhwc,)
        except RuntimeError as e:
            logger.error(f"Failed to stack processed images: {e}")
            return (image,)
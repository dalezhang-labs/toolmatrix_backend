"""Image tools service — background removal (GPT-4o-mini vision + Pillow) and smart resize/crop.

Background removal: GPT-4o-mini identifies the product bounding region, then Pillow
applies a simple white-background composite. Fast (~3-5s total).
Smart resize: algorithm-based crop (center) + optional AI extend (GPT Image outpainting).
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import urllib.request
from io import BytesIO
from typing import Literal

from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

# Preset aspect ratios for e-commerce platforms
PRESETS = {
    "1:1": (1, 1),
    "4:3": (4, 3),
    "3:2": (3, 2),
    "3:4": (3, 4),
    "2:3": (2, 3),
    "16:9": (16, 9),
    "9:16": (9, 16),
}


# ── Background Removal (GPT-4o-mini vision + Pillow) ─────────────────────

async def remove_background(image_bytes: bytes, output_format: str = "png") -> bytes:
    """Remove background using GPT-4o-mini for segmentation + Pillow for compositing.
    
    Pipeline:
    1. Send image to GPT-4o-mini vision → get polygon coordinates of the main subject
    2. Create mask from polygon
    3. Apply mask to isolate subject on white/transparent background
    
    Total time: ~3-5 seconds.
    """
    from backend.tools.imagelingo.services.gpt_image_service import _get_client

    t0 = time.perf_counter()

    # Prepare image
    img = Image.open(BytesIO(image_bytes))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    orig_size = img.size

    # Resize for API (max 1024px to save tokens)
    max_dim = 1024
    scale = 1.0
    if max(img.size) > max_dim:
        scale = max_dim / max(img.size)
        new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
        api_img = img.resize(new_size, Image.LANCZOS)
    else:
        api_img = img

    api_w, api_h = api_img.size

    # Convert to base64 for vision API
    buf = BytesIO()
    api_img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()

    # Step 1: GPT-4o-mini vision — get segmentation polygon
    client = _get_client()

    prompt = f"""Analyze this product image ({api_w}x{api_h} pixels).
Return a JSON object with a polygon outlining the main product/subject.
The polygon should tightly follow the edges of the product.

Return format:
{{"polygon": [[x1,y1], [x2,y2], ...], "has_clear_subject": true}}

Rules:
- Coordinates are in pixels relative to the image dimensions ({api_w}x{api_h})
- Include 12-20 points for a smooth outline
- Follow the product edges closely
- If no clear subject exists, set has_clear_subject to false and return an empty polygon"""

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}},
        ]}],
        response_format={"type": "json_object"},
        max_tokens=800,
    )

    text = response.choices[0].message.content or "{}"
    try:
        data = json.loads(text)
        polygon = data.get("polygon", [])
        has_subject = data.get("has_clear_subject", True)
    except json.JSONDecodeError:
        logger.error("Segmentation parse failed: %s", text[:200])
        polygon = []
        has_subject = False

    logger.info("Segmentation: %d polygon points, has_subject=%s (%.2fs)",
                len(polygon), has_subject, time.perf_counter() - t0)

    # Step 2: Create mask and composite
    if not polygon or len(polygon) < 3 or not has_subject:
        # Fallback: return original image on white background (no segmentation possible)
        logger.warning("No valid polygon, returning original on white bg")
        result = _simple_white_bg(img)
    else:
        # Scale polygon back to original image size
        if scale != 1.0:
            polygon = [[int(x / scale), int(y / scale)] for x, y in polygon]

        result = _apply_polygon_mask(img, polygon, output_format)

    # Encode output
    buf = BytesIO()
    if output_format == "png":
        result.save(buf, format="PNG", optimize=True)
    else:
        if result.mode == "RGBA":
            bg = Image.new("RGB", result.size, (255, 255, 255))
            bg.paste(result, mask=result.split()[3])
            result = bg
        elif result.mode != "RGB":
            result = result.convert("RGB")
        result.save(buf, format="JPEG", quality=92)

    elapsed = time.perf_counter() - t0
    logger.info("Background removal complete: %.2fs, output=%d bytes", elapsed, buf.tell())
    return buf.getvalue()


def _apply_polygon_mask(img: Image.Image, polygon: list, output_format: str) -> Image.Image:
    """Create a smooth mask from polygon and apply to image."""
    w, h = img.size

    # Create mask from polygon
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    # Convert polygon to flat tuple list
    poly_tuples = [(int(p[0]), int(p[1])) for p in polygon if len(p) >= 2]
    if len(poly_tuples) >= 3:
        draw.polygon(poly_tuples, fill=255)

    # Smooth the mask edges with gaussian blur for natural look
    mask = mask.filter(ImageFilter.GaussianBlur(radius=3))

    # Expand mask slightly to avoid cutting into the product
    # Dilate by applying threshold after blur
    mask = mask.point(lambda x: 255 if x > 30 else 0)
    # Re-blur for smooth edges
    mask = mask.filter(ImageFilter.GaussianBlur(radius=2))

    if output_format == "png":
        # RGBA with transparency
        result = img.convert("RGBA")
        result.putalpha(mask)
    else:
        # White background
        bg = Image.new("RGB", (w, h), (255, 255, 255))
        bg.paste(img, mask=mask)
        result = bg

    return result


def _simple_white_bg(img: Image.Image) -> Image.Image:
    """Fallback: just return the image as-is (no segmentation)."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


# ── Smart Resize / Crop ──────────────────────────────────────────────────

def _compute_crop_box(
    src_w: int, src_h: int, target_ratio: float
) -> tuple[int, int, int, int]:
    """Compute center crop box to achieve target aspect ratio."""
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        return (offset, 0, offset + new_w, src_h)
    else:
        new_h = int(src_w / target_ratio)
        offset = (src_h - new_h) // 2
        return (0, offset, src_w, offset + new_h)


def _compute_pad_box(
    src_w: int, src_h: int, target_ratio: float
) -> tuple[int, int, tuple[int, int]]:
    """Compute padding needed to achieve target aspect ratio."""
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_h = int(src_w / target_ratio)
        new_w = src_w
        pad_x = 0
        pad_y = (new_h - src_h) // 2
    else:
        new_w = int(src_h * target_ratio)
        new_h = src_h
        pad_x = (new_w - src_w) // 2
        pad_y = 0
    return new_w, new_h, (pad_x, pad_y)


async def smart_resize(
    image_bytes: bytes,
    target_ratio: str,
    mode: Literal["crop", "pad", "ai_extend"] = "crop",
    output_size: int | None = None,
    bg_color: str = "#FFFFFF",
) -> bytes:
    """Resize image to target aspect ratio.

    Modes:
    - crop: center crop to target ratio (default, fast, free)
    - pad: add solid color padding to reach target ratio
    - ai_extend: use GPT Image to outpaint/extend the image (costs credits)
    """
    t0 = time.perf_counter()

    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    src_w, src_h = img.size

    # Parse target ratio
    if target_ratio in PRESETS:
        rw, rh = PRESETS[target_ratio]
    else:
        parts = target_ratio.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid ratio format: {target_ratio}. Use 'W:H' like '4:3'.")
        rw, rh = int(parts[0]), int(parts[1])

    ratio = rw / rh
    current_ratio = src_w / src_h

    if abs(current_ratio - ratio) / ratio < 0.02:
        result = img
    elif mode == "crop":
        box = _compute_crop_box(src_w, src_h, ratio)
        result = img.crop(box)
    elif mode == "pad":
        new_w, new_h, (pad_x, pad_y) = _compute_pad_box(src_w, src_h, ratio)
        color = _parse_hex_color(bg_color)
        canvas = Image.new("RGB", (new_w, new_h), color)
        canvas.paste(img, (pad_x, pad_y))
        result = canvas
    elif mode == "ai_extend":
        result_bytes = await _ai_extend(image_bytes, img, ratio, output_size)
        logger.info("AI extend: %.2fs", time.perf_counter() - t0)
        return result_bytes
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Apply output_size constraint
    if output_size:
        w, h = result.size
        if max(w, h) > output_size:
            s = output_size / max(w, h)
            result = result.resize((int(w * s), int(h * s)), Image.LANCZOS)

    buf = BytesIO()
    result.save(buf, format="JPEG", quality=92, optimize=True)
    out = buf.getvalue()

    logger.info("Smart resize (%s): %dx%d -> %dx%d in %.2fs",
                mode, src_w, src_h, result.size[0], result.size[1], time.perf_counter() - t0)
    return out


def _parse_hex_color(hex_str: str) -> tuple[int, int, int]:
    """Parse hex color string to RGB tuple."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    if len(hex_str) != 6:
        return (255, 255, 255)
    return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


async def _ai_extend(
    image_bytes: bytes, img: Image.Image, target_ratio: float, output_size: int | None
) -> bytes:
    """Use GPT Image to extend/outpaint image to target ratio."""
    from backend.tools.imagelingo.services.gpt_image_service import _call_image_edit

    src_w, src_h = img.size

    if target_ratio > 1.18:
        api_size = "1536x1024"
    elif target_ratio < 0.85:
        api_size = "1024x1536"
    else:
        api_size = "1024x1024"

    api_w, api_h = map(int, api_size.split("x"))
    s = min(api_w / src_w, api_h / src_h)
    new_w, new_h = int(src_w * s), int(src_h * s)
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (api_w, api_h), (255, 255, 255))
    paste_x = (api_w - new_w) // 2
    paste_y = (api_h - new_h) // 2
    canvas.paste(resized, (paste_x, paste_y))

    buf = BytesIO()
    canvas.save(buf, format="JPEG", quality=90)
    prepared_bytes = buf.getvalue()

    prompt = (
        "Extend this product image naturally to fill the entire canvas. "
        "The white/empty areas around the product should be filled with a clean, "
        "professional background that matches the existing image style. "
        "Keep the product exactly as-is, only extend the background/surroundings."
    )

    result_bytes = await _call_image_edit(prepared_bytes, prompt, "high", api_size)

    if output_size:
        result_img = Image.open(BytesIO(result_bytes))
        w, h = result_img.size
        if max(w, h) > output_size:
            s = output_size / max(w, h)
            result_img = result_img.resize((int(w * s), int(h * s)), Image.LANCZOS)
        buf = BytesIO()
        result_img.save(buf, format="JPEG", quality=92)
        result_bytes = buf.getvalue()

    return result_bytes


# ── Download helper ──────────────────────────────────────────────────────

def download_image(url: str, max_size: int = 10 * 1024 * 1024) -> bytes:
    """Download image from URL with size limit."""
    req = urllib.request.Request(url, headers={"User-Agent": "ImageLingo/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read(max_size + 1)
    if len(data) > max_size:
        raise ValueError(f"Image too large (>{max_size // 1024 // 1024}MB)")
    return data

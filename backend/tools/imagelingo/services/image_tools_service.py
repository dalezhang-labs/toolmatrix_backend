"""Image tools service — background removal (FLUX.1-Kontext-pro) and smart resize/crop.

Background removal: uses FLUX.1-Kontext-pro via images.generate with image reference (~5s).
Smart resize: algorithm-based crop (center) + optional AI extend (GPT Image outpainting).
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
import urllib.request
from io import BytesIO
from typing import Literal

from PIL import Image

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

# FLUX Kontext uses the same Azure endpoint and key as GPT models
AZURE_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_ENDPOINT",
    "https://foundry-llm-zg.services.ai.azure.com/openai/v1",
)
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
FLUX_DEPLOYMENT = "FLUX.1-Kontext-pro"


def _get_flux_client():
    """Get OpenAI client configured for FLUX.1-Kontext-pro on Azure Foundry."""
    from openai import OpenAI
    return OpenAI(base_url=AZURE_ENDPOINT, api_key=AZURE_API_KEY)


# ── Background Removal (FLUX.1-Kontext-pro) ─────────────────────────────

async def remove_background(image_bytes: bytes, output_format: str = "png") -> bytes:
    """Remove background from image using FLUX.1-Kontext-pro.
    Uses images.generate with image reference. ~5s processing time.
    """
    t0 = time.perf_counter()

    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("P",):
        img = img.convert("RGBA")

    orig_size = img.size

    # Resize to max 1024px
    max_dim = 1024
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Convert to RGB PNG for API
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Determine output size
    w, h = img.size
    aspect = w / h
    if aspect > 1.3:
        api_size = "1536x1024"
    elif aspect < 0.77:
        api_size = "1024x1536"
    else:
        api_size = "1024x1024"

    # Encode to base64
    buf = BytesIO()
    img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    prompt = (
        "Remove the background from this image completely. "
        "Keep only the main product/subject with clean, precise edges. "
        "Replace the background with pure solid white (#FFFFFF). "
        "Do not alter the product at all. [img-0]"
    )

    # Call FLUX.1-Kontext-pro via images.generate with image reference
    client = _get_flux_client()

    response = await asyncio.to_thread(
        client.images.generate,
        model=FLUX_DEPLOYMENT,
        prompt=prompt,
        n=1,
        size=api_size,
        extra_body={
            "image": [f"data:image/png;base64,{img_b64}"]
        },
    )

    # Extract result
    result_b64 = response.data[0].b64_json
    if not result_b64:
        if response.data[0].url:
            req = urllib.request.Request(response.data[0].url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                result_bytes = resp.read()
        else:
            raise ValueError("FLUX returned no image data")
    else:
        result_bytes = base64.b64decode(result_b64)

    elapsed = time.perf_counter() - t0
    logger.info("Background removal (FLUX Kontext): %.2fs", elapsed)

    # Restore to original size if needed
    result_img = Image.open(BytesIO(result_bytes))
    if result_img.size != orig_size:
        result_img = result_img.resize(orig_size, Image.LANCZOS)

    # Encode output
    out_buf = BytesIO()
    if output_format == "png":
        if result_img.mode != "RGB":
            result_img = result_img.convert("RGB")
        result_img.save(out_buf, format="PNG", optimize=True)
    else:
        if result_img.mode != "RGB":
            result_img = result_img.convert("RGB")
        result_img.save(out_buf, format="JPEG", quality=92)

    return out_buf.getvalue()


# ── Smart Resize / Crop ──────────────────────────────────────────────────

def _compute_crop_box(src_w, src_h, target_ratio):
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        return (offset, 0, offset + new_w, src_h)
    else:
        new_h = int(src_w / target_ratio)
        offset = (src_h - new_h) // 2
        return (0, offset, src_w, offset + new_h)


def _compute_pad_box(src_w, src_h, target_ratio):
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
    """Resize image to target aspect ratio."""
    t0 = time.perf_counter()

    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    src_w, src_h = img.size

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

    if output_size:
        w, h = result.size
        if max(w, h) > output_size:
            s = output_size / max(w, h)
            result = result.resize((int(w * s), int(h * s)), Image.LANCZOS)

    buf = BytesIO()
    result.save(buf, format="JPEG", quality=92, optimize=True)
    logger.info("Smart resize (%s): %dx%d -> %dx%d in %.2fs",
                mode, src_w, src_h, result.size[0], result.size[1], time.perf_counter() - t0)
    return buf.getvalue()


def _parse_hex_color(hex_str: str) -> tuple:
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    if len(hex_str) != 6:
        return (255, 255, 255)
    return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


async def _ai_extend(image_bytes, img, target_ratio, output_size):
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

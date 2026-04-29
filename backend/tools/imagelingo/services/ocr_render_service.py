"""OCR + Render Service — text-accurate image translation.
Pipeline: GPT-4o-mini vision (OCR + translate) → Pillow (render text on image).
No garbled characters because text is rendered with real fonts, not AI-generated pixels.
"""
from __future__ import annotations

import base64
import datetime
import json
import logging
import os
import time
import uuid
import urllib.request
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

AZURE_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_ENDPOINT",
    "https://foundry-llm-zg.services.ai.azure.com/openai/v1",
)
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")

# CJK font path — bundled in Docker image
FONT_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
]


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Get a CJK-capable font at the given size."""
    for path in FONT_PATHS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    # Fallback: try system default
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _download_image(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ImageLingo/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


async def _ocr_and_translate(image_bytes: bytes, target_language: str) -> list[dict]:
    """Use GPT-4o-mini vision to detect text regions and translate them.
    Returns list of: {x, y, w, h, original, translated, font_size, color}
    """
    from openai import OpenAI

    client = OpenAI(base_url=AZURE_ENDPOINT, api_key=AZURE_API_KEY)
    b64 = base64.b64encode(image_bytes).decode()

    # Get image dimensions for coordinate reference
    img = Image.open(BytesIO(image_bytes))
    width, height = img.size

    prompt = f"""Analyze this product image ({width}x{height} pixels). Find ALL text regions and translate them to {target_language}.

Return a JSON array. Each element must have:
- "x": left position in pixels (integer)
- "y": top position in pixels (integer)  
- "w": width of text region in pixels (integer)
- "h": height of text region in pixels (integer)
- "original": the original text exactly as shown
- "translated": accurate {target_language} translation
- "font_size": estimated font size in pixels (integer)
- "color": text color as hex string (e.g. "#000000")
- "bg_color": background color behind the text as hex string

Rules:
- Include EVERY piece of visible text, even small labels
- Coordinates must be precise pixel positions within the {width}x{height} image
- Keep brand names in original language
- For Chinese: use standard Simplified Chinese only
- Return ONLY the JSON array, no other text"""

    import asyncio
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
            ]},
        ],
        response_format={"type": "json_object"},
        max_tokens=4000,
    )

    text = response.choices[0].message.content or "[]"
    # Parse JSON — handle both {"regions": [...]} and bare [...]
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            regions = data.get("regions") or data.get("text_regions") or data.get("texts") or []
        elif isinstance(data, list):
            regions = data
        else:
            regions = []
    except json.JSONDecodeError:
        logger.error("Failed to parse OCR response: %s", text[:200])
        regions = []

    logger.info("OCR found %d text regions", len(regions))
    return regions


def _render_translations(image_bytes: bytes, regions: list[dict]) -> bytes:
    """Replace original text with translated text on the image using Pillow."""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    for region in regions:
        try:
            x = int(region.get("x", 0))
            y = int(region.get("y", 0))
            w = int(region.get("w", 100))
            h = int(region.get("h", 30))
            translated = region.get("translated", "")
            font_size = int(region.get("font_size", 20))
            color = region.get("color", "#000000")
            bg_color = region.get("bg_color", "#FFFFFF")

            if not translated:
                continue

            # Step 1: Cover original text with background color
            draw.rectangle([x, y, x + w, y + h], fill=bg_color)

            # Step 2: Render translated text
            font = _get_font(font_size)

            # Auto-fit: reduce font size if text is too wide
            bbox = draw.textbbox((0, 0), translated, font=font)
            text_w = bbox[2] - bbox[0]
            while text_w > w * 0.95 and font_size > 8:
                font_size -= 1
                font = _get_font(font_size)
                bbox = draw.textbbox((0, 0), translated, font=font)
                text_w = bbox[2] - bbox[0]

            # Center text in the region
            text_h = bbox[3] - bbox[1]
            text_x = x + (w - text_w) // 2
            text_y = y + (h - text_h) // 2

            draw.text((text_x, text_y), translated, fill=color, font=font)

        except Exception as e:
            logger.warning("Failed to render region: %s", e)
            continue

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def _upload_to_s3(image_bytes: bytes, target_language: str) -> str | None:
    """Upload to S3, return presigned URL."""
    cfg = {
        "access_key": os.environ.get("AWS_ACCESS_KEY_ID", ""),
        "secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        "bucket": os.environ.get("S3_BUCKET", ""),
        "region": os.environ.get("S3_REGION", "us-east-1"),
    }
    if not cfg["access_key"] or not cfg["bucket"]:
        return None

    from backend.shared.s3_utils import sign_s3_upload, generate_presigned_url
    import httpx

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = str(uuid.uuid4())[:8]
    s3_key = f"imagelingo/translated_ocr/{ts}_{uid}_{target_language}.png"

    signed = sign_s3_upload(
        file_bytes=image_bytes, bucket=cfg["bucket"], object_key=s3_key,
        region=cfg["region"], access_key=cfg["access_key"],
        secret_key=cfg["secret_key"], content_type="image/png",
        date=datetime.datetime.now(datetime.timezone.utc),
    )
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(signed["url"], headers=signed["headers"], content=image_bytes)
    if resp.status_code not in (200, 201):
        return None

    return generate_presigned_url(
        bucket=cfg["bucket"], object_key=s3_key, region=cfg["region"],
        access_key=cfg["access_key"], secret_key=cfg["secret_key"], expires_in=86400,
    )


async def translate_image(image_url: str, target_language: str, **kwargs) -> str:
    """OCR + Render pipeline: detect text → translate → render with real fonts."""
    t0 = time.perf_counter()

    # Download
    image_bytes = _download_image(image_url)
    logger.info("OCR-Render: downloaded %d bytes in %.1fs", len(image_bytes), time.perf_counter() - t0)

    # OCR + Translate (GPT-4o-mini vision)
    t1 = time.perf_counter()
    regions = await _ocr_and_translate(image_bytes, target_language)
    logger.info("OCR-Render: OCR+translate in %.1fs, %d regions", time.perf_counter() - t1, len(regions))

    if not regions:
        raise ValueError("No text regions detected in the image")

    # Render
    t2 = time.perf_counter()
    result_bytes = _render_translations(image_bytes, regions)
    logger.info("OCR-Render: render in %.1fs, %d bytes", time.perf_counter() - t2, len(result_bytes))

    # Upload to S3
    s3_url = await _upload_to_s3(result_bytes, target_language)
    if s3_url:
        logger.info("OCR-Render: total %.1fs", time.perf_counter() - t0)
        return s3_url

    raise ValueError("Failed to upload OCR-rendered image")

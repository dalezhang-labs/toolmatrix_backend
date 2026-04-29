"""GPT Image Service — OCR-assisted image translation.
Pipeline: GPT-4o-mini vision (OCR + translate) → GPT Image edit (render with precise translation table).
The OCR step gives GPT Image exact text-to-translation mappings, eliminating garbled characters.
"""
from __future__ import annotations

import asyncio
import base64
import datetime
import json
import logging
import os
import time
import uuid
import urllib.request
from io import BytesIO

logger = logging.getLogger(__name__)

AZURE_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_ENDPOINT",
    "https://foundry-llm-zg.services.ai.azure.com/openai/v1",
)
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_IMAGE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_IMAGE_DEPLOYMENT", "gpt-image-1.5")

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(base_url=AZURE_ENDPOINT, api_key=AZURE_API_KEY, max_retries=3)
    return _client


def _download_and_resize(url: str, max_dim: int = 1024) -> bytes:
    """Download image, resize, compress as JPEG."""
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"User-Agent": "ImageLingo/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    try:
        from PIL import Image
        img = Image.open(BytesIO(raw))
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)), Image.LANCZOS)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        out = buf.getvalue()
        logger.info("Download+resize %.2fs (%d→%d bytes)", time.perf_counter() - t0, len(raw), len(out))
        return out
    except Exception:
        return raw


# ── Step 1: OCR + Translate via GPT-4o vision ───────────────────────────

async def _ocr_and_translate(image_bytes: bytes, target_language: str) -> list[dict]:
    """Use GPT-4o vision to read all text with style info and produce exact translations.
    Returns list of {"original", "translated", "style"} dicts.
    """
    client = _get_client()
    b64 = base64.b64encode(image_bytes).decode()

    from PIL import Image
    img = Image.open(BytesIO(image_bytes))
    w, h = img.size

    prompt = f"""You are an expert product image localizer. Analyze this {w}×{h} product image.

For EVERY piece of visible text, provide:
1. The exact original text
2. An accurate {target_language} translation
3. A description of the text's visual style (font weight, approximate size, color, case style)

Return a JSON object:
{{"translations": [
  {{"original": "EXACT TEXT", "translated": "{target_language} translation", "style": "bold, large, dark gray, uppercase"}}
]}}

CRITICAL RULES:
- Include ALL text: headings, subheadings, labels, captions, bullet points
- Brand names / product model names → keep in original language, set translated = original
- For Simplified Chinese (简体中文): every single character must be a real, correct Chinese character. Double-check each character.
- Translations must sound natural to a native {target_language} speaker
- Style description helps preserve the visual feel during rendering"""

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
        ]}],
        response_format={"type": "json_object"},
        max_tokens=3000,
    )

    text = response.choices[0].message.content or "{}"
    try:
        data = json.loads(text)
        pairs = data.get("translations") or data.get("text") or []
        if isinstance(data, list):
            pairs = data
    except json.JSONDecodeError:
        logger.error("OCR parse failed: %s", text[:200])
        pairs = []

    logger.info("OCR (GPT-4o) found %d text pairs for %s", len(pairs), target_language)
    for p in pairs:
        logger.info("  '%s' → '%s' [%s]", p.get("original",""), p.get("translated",""), p.get("style",""))
    return pairs


# ── Step 2: Build precise prompt from translation table ──────────────────

def _build_prompt(target_language: str, translation_pairs: list[dict]) -> str:
    """Build a GPT Image edit prompt with exact text-to-translation mappings and style hints."""
    if not translation_pairs:
        return (
            f"Translate ALL visible text in this image into {target_language}. "
            "Keep the exact same layout, design, colors, and positions. "
            "Only replace text, do not change anything else."
        )

    # Build detailed translation table with style info
    table_lines = []
    for i, pair in enumerate(translation_pairs, 1):
        orig = pair.get("original", "").strip()
        trans = pair.get("translated", "").strip()
        style = pair.get("style", "")
        if orig and trans:
            if orig == trans:
                table_lines.append(f'  {i}. "{orig}" → KEEP AS IS (brand name)')
            else:
                style_hint = f" [{style}]" if style else ""
                table_lines.append(f'  {i}. "{orig}" → "{trans}"{style_hint}')

    table = "\n".join(table_lines)

    return (
        f"You are a professional product image localizer. Replace ONLY the text in this image.\n\n"
        f"EXACT TRANSLATION TABLE (use these translations character-by-character, do NOT modify them):\n"
        f"{table}\n\n"
        f"MANDATORY RULES — violating any rule means failure:\n"
        f"1. PIXEL-PERFECT PRESERVATION: The image layout, product photos, graphics, backgrounds, colors, shadows, and all non-text elements must be IDENTICAL to the original. Not similar — identical.\n"
        f"2. CHARACTER ACCURACY: Copy each translated character EXACTLY from the table above. For CJK characters (Chinese/Japanese/Korean), every stroke must be correct. If unsure about a character, use the exact Unicode character from the table.\n"
        f"3. FONT STYLE MATCHING: Match the original text's font weight (bold/regular), size, color, letter-spacing, and visual style as closely as possible.\n"
        f"4. POSITION PRESERVATION: Each translated text must occupy the same position and area as the original text it replaces.\n"
        f"5. NO ADDITIONS: Do not add any text, watermarks, or elements that are not in the original image.\n"
        f"6. NO REMOVALS: Do not remove any non-text visual elements.\n"
        f"7. BRAND NAMES: Items marked 'KEEP AS IS' must remain in their original language.\n\n"
        f"This is a surgical text replacement operation. The output image should be indistinguishable from the original except for the translated text."
    )


# ── Step 3: GPT Image edit with precise prompt ──────────────────────────

async def _call_image_edit(image_bytes: bytes, prompt: str, quality: str, size: str) -> bytes:
    """Call Azure GPT Image edit REST API, return result image bytes."""
    import httpx

    endpoint = AZURE_ENDPOINT.rstrip("/")
    for suffix in ("/openai/v1", "/v1"):
        if endpoint.endswith(suffix):
            endpoint = endpoint[: -len(suffix)]
            break

    edit_url = f"{endpoint}/openai/deployments/{AZURE_IMAGE_DEPLOYMENT}/images/edits?api-version=2025-04-01-preview"

    t0 = time.perf_counter()
    max_retries = 3
    resp = None

    async with httpx.AsyncClient(timeout=180) as http_client:
        for attempt in range(max_retries):
            resp = await http_client.post(
                edit_url,
                files={"image": ("source.jpg", image_bytes, "image/jpeg")},
                data={
                    "prompt": prompt,
                    "n": "1",
                    "size": size,
                    "quality": quality,
                    "input_fidelity": "high",
                },
                headers={"api-key": AZURE_API_KEY},
            )
            if resp.status_code == 200:
                break
            if resp.status_code in (429, 500, 502, 503) and attempt < max_retries - 1:
                wait = (attempt + 1) * 10
                logger.warning("Azure %d on attempt %d, retrying in %ds", resp.status_code, attempt + 1, wait)
                await asyncio.sleep(wait)
                continue
            break

    elapsed = time.perf_counter() - t0
    logger.info("Image edit %.1fs (status=%d, attempts=%d)", elapsed, resp.status_code if resp else 0, attempt + 1)

    if not resp or resp.status_code != 200:
        detail = resp.text[:300] if resp else "No response"
        raise ValueError(f"GPT Image edit failed ({resp.status_code if resp else 0}): {detail}")

    result = resp.json()
    b64_data = result.get("data", [{}])[0].get("b64_json")
    if not b64_data:
        raise ValueError("GPT Image edit returned no image data")

    return base64.b64decode(b64_data)


# ── S3 upload ────────────────────────────────────────────────────────────

async def _upload_to_s3(image_bytes: bytes, target_language: str) -> str | None:
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
    s3_key = f"imagelingo/translated/{ts}_{uid}_{target_language}.png"

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


# ── Main entry point ────────────────────────────────────────────────────

async def translate_image(
    image_url: str,
    target_language: str,
    quality: str = "high",
    size: str = "1024x1024",
) -> str:
    """OCR-assisted image translation pipeline:
    1. GPT-4o-mini vision → read all text + translate (fast, accurate, cheap)
    2. Build precise prompt with exact translation table
    3. GPT Image edit → render translations on image (uses the table, not guessing)
    """
    if not AZURE_API_KEY:
        raise ValueError("AZURE_OPENAI_API_KEY is not set")

    t_total = time.perf_counter()
    azure_quality = "high"  # always high for best text rendering
    max_dim = 1024

    # Step 1: Download image
    image_bytes = _download_and_resize(image_url, max_dim=max_dim)

    # Step 2: OCR + Translate (GPT-4o-mini, ~3-5s, very cheap)
    t_ocr = time.perf_counter()
    pairs = await _ocr_and_translate(image_bytes, target_language)
    logger.info("OCR+translate: %.1fs, %d pairs", time.perf_counter() - t_ocr, len(pairs))

    # Step 3: Build precise prompt
    prompt = _build_prompt(target_language, pairs)
    logger.info("Prompt length: %d chars, %d translation pairs", len(prompt), len(pairs))

    # Step 4: GPT Image edit with precise prompt
    result_bytes = await _call_image_edit(image_bytes, prompt, azure_quality, size)
    logger.info("Total pipeline: %.1fs", time.perf_counter() - t_total)

    # Step 5: Upload to S3
    s3_url = await _upload_to_s3(result_bytes, target_language)
    if s3_url:
        return s3_url

    # Fallback
    image_id = str(uuid.uuid4())[:12]
    os.makedirs("/tmp/imagelingo_results", exist_ok=True)
    path = f"/tmp/imagelingo_results/{image_id}.png"
    with open(path, "wb") as f:
        f.write(result_bytes)
    return f"/api/imagelingo/translate/results/{image_id}.png"

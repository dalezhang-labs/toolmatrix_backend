"""Image tools routes — background removal and smart resize/crop."""
from __future__ import annotations

import datetime
import logging
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Literal, Optional

from backend.tools.imagelingo.services.image_tools_service import (
    remove_background,
    smart_resize,
    download_image,
    PRESETS,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request / Response models ────────────────────────────────────────────

class RemoveBgUrlRequest(BaseModel):
    image_url: str
    output_format: str = "png"  # png (transparent) or jpg (white bg)


class ResizeUrlRequest(BaseModel):
    image_url: str
    target_ratio: str  # "1:1", "4:3", "3:2", "3:4", "2:3", "16:9", "9:16"
    mode: Literal["crop", "pad", "ai_extend"] = "crop"
    output_size: Optional[int] = None  # max dimension in px
    bg_color: str = "#FFFFFF"  # for pad mode


class ImageToolResponse(BaseModel):
    url: str
    key: str


# ── Helpers ──────────────────────────────────────────────────────────────

async def _upload_result_to_s3(
    image_bytes: bytes, prefix: str, ext: str = "png"
) -> tuple[str, str]:
    """Upload processed image to S3, return (presigned_url, s3_key)."""
    from backend.shared.s3_utils import sign_s3_upload, generate_presigned_url
    import httpx

    cfg = {
        "access_key": os.environ.get("AWS_ACCESS_KEY_ID", ""),
        "secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        "bucket": os.environ.get("S3_BUCKET", ""),
        "region": os.environ.get("S3_REGION", "us-east-2"),
    }
    if not cfg["access_key"] or not cfg["bucket"]:
        raise HTTPException(500, "S3 not configured")

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = str(uuid.uuid4())[:8]
    s3_key = f"imagelingo/{prefix}/{ts}_{uid}.{ext}"

    content_type = "image/png" if ext == "png" else "image/jpeg"

    signed = sign_s3_upload(
        file_bytes=image_bytes,
        bucket=cfg["bucket"],
        object_key=s3_key,
        region=cfg["region"],
        access_key=cfg["access_key"],
        secret_key=cfg["secret_key"],
        content_type=content_type,
        date=datetime.datetime.now(datetime.timezone.utc),
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(signed["url"], headers=signed["headers"], content=image_bytes)

    if resp.status_code not in (200, 201):
        raise HTTPException(502, f"S3 upload failed (HTTP {resp.status_code})")

    presigned = generate_presigned_url(
        bucket=cfg["bucket"],
        object_key=s3_key,
        region=cfg["region"],
        access_key=cfg["access_key"],
        secret_key=cfg["secret_key"],
        expires_in=86400,
    )
    return presigned, s3_key


# ── Background Removal Routes ────────────────────────────────────────────

@router.post("/remove-bg", response_model=ImageToolResponse)
async def remove_bg_from_url(req: RemoveBgUrlRequest):
    """Remove background from image URL. Returns processed image URL."""
    if not req.image_url.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid image URL")

    try:
        image_bytes = download_image(req.image_url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(400, "Failed to download image")

    fmt = req.output_format.lower()
    if fmt not in ("png", "jpg", "jpeg"):
        raise HTTPException(400, "output_format must be 'png' or 'jpg'")

    result = await remove_background(image_bytes, output_format=fmt)
    ext = "png" if fmt == "png" else "jpg"
    url, key = await _upload_result_to_s3(result, "remove-bg", ext)
    return ImageToolResponse(url=url, key=key)


@router.post("/remove-bg/upload", response_model=ImageToolResponse)
async def remove_bg_from_upload(
    file: UploadFile = File(...),
    output_format: str = Form("png"),
):
    """Remove background from uploaded image file."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 10MB)")

    fmt = output_format.lower()
    if fmt not in ("png", "jpg", "jpeg"):
        raise HTTPException(400, "output_format must be 'png' or 'jpg'")

    result = await remove_background(content, output_format=fmt)
    ext = "png" if fmt == "png" else "jpg"
    url, key = await _upload_result_to_s3(result, "remove-bg", ext)
    return ImageToolResponse(url=url, key=key)


# ── Smart Resize Routes ──────────────────────────────────────────────────

@router.get("/resize/presets")
async def get_resize_presets():
    """Return available aspect ratio presets."""
    return {
        "presets": [
            {"key": k, "width": v[0], "height": v[1], "label": k}
            for k, v in PRESETS.items()
        ]
    }


@router.post("/resize", response_model=ImageToolResponse)
async def resize_from_url(req: ResizeUrlRequest):
    """Smart resize image from URL to target aspect ratio."""
    if not req.image_url.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid image URL")

    if req.target_ratio not in PRESETS:
        # Validate custom ratio format
        parts = req.target_ratio.split(":")
        if len(parts) != 2:
            raise HTTPException(400, f"Invalid ratio: {req.target_ratio}. Use 'W:H' format.")
        try:
            int(parts[0])
            int(parts[1])
        except ValueError:
            raise HTTPException(400, "Ratio values must be integers")

    if req.output_size and (req.output_size < 100 or req.output_size > 4096):
        raise HTTPException(400, "output_size must be between 100 and 4096")

    try:
        image_bytes = download_image(req.image_url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(400, "Failed to download image")

    result = await smart_resize(
        image_bytes=image_bytes,
        target_ratio=req.target_ratio,
        mode=req.mode,
        output_size=req.output_size,
        bg_color=req.bg_color,
    )
    url, key = await _upload_result_to_s3(result, "resized", "jpg")
    return ImageToolResponse(url=url, key=key)


@router.post("/resize/upload", response_model=ImageToolResponse)
async def resize_from_upload(
    file: UploadFile = File(...),
    target_ratio: str = Form(...),
    mode: str = Form("crop"),
    output_size: Optional[int] = Form(None),
    bg_color: str = Form("#FFFFFF"),
):
    """Smart resize uploaded image to target aspect ratio."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 10MB)")

    if mode not in ("crop", "pad", "ai_extend"):
        raise HTTPException(400, "mode must be 'crop', 'pad', or 'ai_extend'")

    if output_size and (output_size < 100 or output_size > 4096):
        raise HTTPException(400, "output_size must be between 100 and 4096")

    result = await smart_resize(
        image_bytes=content,
        target_ratio=target_ratio,
        mode=mode,
        output_size=output_size,
        bg_color=bg_color,
    )
    url, key = await _upload_result_to_s3(result, "resized", "jpg")
    return ImageToolResponse(url=url, key=key)

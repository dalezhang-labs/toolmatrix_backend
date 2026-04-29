"""Shared S3 upload router — serves all tools in the toolmatrix backend.

Endpoints:
  POST /api/shared/s3/upload       — single file upload
  POST /api/shared/s3/upload-batch — batch file upload

Config via environment variables:
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET, S3_REGION
"""
from __future__ import annotations

import datetime
import logging
import os
import uuid
from typing import List, Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.shared.s3_utils import sign_s3_upload

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Shared httpx client
_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


def _s3_config() -> dict:
    return {
        "access_key": os.environ.get("AWS_ACCESS_KEY_ID", ""),
        "secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        "bucket": os.environ.get("S3_BUCKET", ""),
        "region": os.environ.get("S3_REGION", "us-east-2"),
    }


async def _do_upload(
    file_content: bytes,
    original_filename: str,
    content_type: str,
    path_prefix: str,
    custom_filename: Optional[str],
    cfg: dict,
) -> dict:
    """Upload a single file to S3, return metadata dict."""
    file_size = len(file_content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large ({file_size / (1024*1024):.1f}MB, max {MAX_FILE_SIZE // (1024*1024)}MB)")

    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""

    if custom_filename:
        final_name = custom_filename
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = str(uuid.uuid4())[:8]
        final_name = f"{ts}_{uid}.{ext}" if ext else f"{ts}_{uid}"

    prefix = path_prefix.strip("/") if path_prefix else ""
    s3_key = f"{prefix}/{final_name}" if prefix else final_name

    upload_date = datetime.datetime.now(datetime.timezone.utc)
    signed = sign_s3_upload(
        file_bytes=file_content,
        bucket=cfg["bucket"],
        object_key=s3_key,
        region=cfg["region"],
        access_key=cfg["access_key"],
        secret_key=cfg["secret_key"],
        content_type=content_type,
        date=upload_date,
    )

    client = await _get_client()
    resp = await client.put(signed["url"], headers=signed["headers"], content=file_content)

    if resp.status_code not in (200, 201):
        logger.error("S3 upload failed (%d): %s", resp.status_code, resp.text[:300])
        raise HTTPException(502, f"S3 upload failed (HTTP {resp.status_code})")

    url = f"https://{cfg['bucket']}.s3.{cfg['region']}.amazonaws.com/{s3_key}"
    logger.info("S3 upload OK: %s (%d bytes)", url, file_size)

    return {
        "url": url,
        "bucket": cfg["bucket"],
        "key": s3_key,
        "region": cfg["region"],
        "file_size": file_size,
        "content_type": content_type,
        "original_filename": original_filename,
    }


@router.post("/upload")
async def s3_upload(
    file: UploadFile = File(...),
    path_prefix: str = Form("uploads"),
    custom_filename: Optional[str] = Form(None),
):
    """Upload a single file to S3. Returns the public URL."""
    cfg = _s3_config()
    if not cfg["access_key"] or not cfg["bucket"]:
        raise HTTPException(500, "S3 not configured (missing AWS_ACCESS_KEY_ID or S3_BUCKET)")

    content = await file.read()
    ct = file.content_type or "application/octet-stream"
    result = await _do_upload(content, file.filename or "upload", ct, path_prefix, custom_filename, cfg)
    return {"url": result["url"], "data": result}


@router.post("/upload-batch")
async def s3_upload_batch(
    files: List[UploadFile] = File(...),
    path_prefix: str = Form("uploads"),
):
    """Upload multiple files to S3."""
    cfg = _s3_config()
    if not cfg["access_key"] or not cfg["bucket"]:
        raise HTTPException(500, "S3 not configured")

    uploaded, errors = [], []
    for idx, f in enumerate(files):
        try:
            content = await f.read()
            ct = f.content_type or "application/octet-stream"
            result = await _do_upload(content, f.filename or f"file_{idx}", ct, path_prefix, None, cfg)
            uploaded.append(result)
        except Exception as e:
            errors.append({"filename": f.filename, "error": str(e)})

    return {
        "uploaded": uploaded,
        "errors": errors,
        "total": len(files),
        "success_count": len(uploaded),
        "error_count": len(errors),
    }

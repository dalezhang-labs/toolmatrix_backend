"""Lovart Service — image translation via Lovart Agent API.
Optimized: shorter prompts, image standardization, faster polling.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

LOVART_BASE_URL = os.environ.get("LOVART_BASE_URL", "https://lgw.lovart.ai")
LOVART_PREFIX = "/v1/openapi"

_ssl_ctx = ssl.create_default_context()
if os.environ.get("LOVART_INSECURE_SSL") == "1":
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE

# Shorter, more direct prompt = faster Lovart processing
PROMPT_TEMPLATE = (
    "Replace all text in this product image with {target_lang} translation. "
    "Keep the same layout, colors, fonts, and design. Output the translated image."
)


class LovartService:
    def __init__(self):
        from backend.tools.imagelingo.config import validate_lovart
        validate_lovart()
        self.access_key = os.environ["LOVART_ACCESS_KEY"]
        self.secret_key = os.environ["LOVART_SECRET_KEY"]
        self.base_url = LOVART_BASE_URL
        self.prefix = LOVART_PREFIX

    def _sign(self, method: str, path: str) -> dict:
        ts = str(int(time.time()))
        sig = hmac.new(
            self.secret_key.encode(),
            f"{method}\n{path}\n{ts}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-Access-Key": self.access_key,
            "X-Timestamp": ts,
            "X-Signature": sig,
            "X-Signed-Method": method,
            "X-Signed-Path": path,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 DaleToolMatrix/1.0",
        }

    def _request(self, method: str, path: str, body=None, params=None, retries: int = 3) -> dict:
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None

        for attempt in range(retries):
            headers = self._sign(method, path)
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=120, context=_ssl_ctx) as resp:
                    result = json.loads(resp.read().decode())
                break
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                if e.code in (429, 502, 503) and attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise ValueError(f"Lovart HTTP {e.code}: {err_body[:200]}")
            except (urllib.error.URLError, ssl.SSLError, OSError) as e:
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise ValueError(f"Lovart connection failed after {retries} attempts: {e}")
        else:
            raise ValueError("Lovart connection failed")

        if isinstance(result, dict) and result.get("code", 0) != 0:
            raise ValueError(f"Lovart API error: {result.get('message', result)}")
        return result.get("data", result) if isinstance(result, dict) else result

    def _get_or_create_project(self) -> str:
        result = self._request("POST", f"{self.prefix}/project/save", body={
            "project_id": "",
            "canvas": "",
            "project_cover_list": [],
            "pic_count": 0,
            "project_type": 3,
            "project_name": "imagelingo-translations",
        })
        return result.get("project_id", "")

    @staticmethod
    def _extract_image_url(result: dict) -> str | None:
        for item in result.get("items", []):
            for artifact in item.get("artifacts", []):
                if artifact.get("type") == "image":
                    url = artifact.get("content", "")
                    if url:
                        return url
        for item in result.get("items", []):
            for artifact in item.get("artifacts", []):
                url = artifact.get("url") or artifact.get("content") or artifact.get("data")
                if url and isinstance(url, str) and url.startswith("http"):
                    return url
            for att in item.get("attachments", []):
                if isinstance(att, str) and att.startswith("http"):
                    return att
                if isinstance(att, dict):
                    url = att.get("url") or att.get("content")
                    if url and isinstance(url, str) and url.startswith("http"):
                        return url
        return None

    async def translate_image(
        self,
        image_url: str,
        target_language: str,
        source_hint: str = "auto",
        ocr_texts: list[str] | None = None,
    ) -> str:
        project_id = self._get_or_create_project()
        prompt = PROMPT_TEMPLATE.format(target_lang=target_language)

        thread_id = self._request("POST", f"{self.prefix}/chat", body={
            "prompt": prompt,
            "project_id": project_id,
            "attachments": [image_url],
        })["thread_id"]
        logger.info("Lovart chat started: thread_id=%s, target=%s", thread_id, target_language)

        # Faster polling: start at 2s, increase gradually
        for i in range(120):
            wait = 2 if i < 10 else 3 if i < 30 else 5
            await asyncio.sleep(wait)
            status_data = self._request("GET", f"{self.prefix}/chat/status", params={"thread_id": thread_id})
            status = status_data.get("status")
            if status == "done":
                result = self._request("GET", f"{self.prefix}/chat/result", params={"thread_id": thread_id})
                url = self._extract_image_url(result)
                if url:
                    return url
                raise ValueError("Lovart done but no image artifact found")
            if status == "abort":
                raise ValueError("Lovart task aborted")
        raise TimeoutError("Lovart translation timed out after 10 minutes")

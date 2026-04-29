"""AWS S3 Signature V4 signing utility.
Pure Python, no AWS SDK dependency. Used for direct S3 PutObject uploads.
"""
import hashlib
import hmac
import datetime
import urllib.parse
from typing import Dict, Optional


def sign_s3_upload(
    file_bytes: bytes,
    bucket: str,
    object_key: str,
    region: str,
    access_key: str,
    secret_key: str,
    content_type: str,
    date: datetime.datetime,
    acl: Optional[str] = None,
) -> Dict[str, str]:
    """Generate AWS Signature V4 headers for an S3 PutObject request.

    Returns dict with 'url' and 'headers' ready for httpx.put().
    """
    method = "PUT"
    service = "s3"
    host = f"{bucket}.s3.{region}.amazonaws.com"
    endpoint = f"https://{host}/{object_key}"

    amz_date = date.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = date.strftime("%Y%m%d")

    payload_hash = hashlib.sha256(file_bytes).hexdigest()

    # Canonical request
    canonical_uri = f"/{urllib.parse.quote(object_key)}"
    headers_to_sign = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    if acl:
        headers_to_sign["x-amz-acl"] = acl

    sorted_keys = sorted(headers_to_sign.keys())
    canonical_headers = "".join(f"{k}:{headers_to_sign[k]}\n" for k in sorted_keys)
    signed_headers = ";".join(sorted_keys)

    canonical_request = "\n".join([
        method, canonical_uri, "",  # empty query string
        canonical_headers, signed_headers, payload_hash,
    ])

    # String to sign
    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        algorithm, amz_date, credential_scope,
        hashlib.sha256(canonical_request.encode()).hexdigest(),
    ])

    # Signing key
    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    k_date = _sign(f"AWS4{secret_key}".encode(), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

    authorization = (
        f"{algorithm} Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Host": host,
        "Content-Type": content_type,
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
        "Authorization": authorization,
    }
    if acl:
        headers["x-amz-acl"] = acl

    return {"url": endpoint, "headers": headers}

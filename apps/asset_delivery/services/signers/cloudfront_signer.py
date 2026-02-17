# apps/asset_delivery/services/signers/cloudfront_signer.py

from __future__ import annotations

import datetime
import json
import time
from urllib.parse import urlparse
from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings
from botocore.signers import CloudFrontSigner
import rsa
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SignedResult:
    url: str
    expires_in: int


@lru_cache(maxsize=1)
def _load_cf_private_key_cached() -> rsa.PrivateKey:
    path = getattr(settings, "CLOUDFRONT_PRIVATE_KEY_PATH", "") or ""
    if not path:
        raise RuntimeError("CLOUDFRONT_PRIVATE_KEY_PATH is empty")

    try:
        with open(path, "rb") as f:
            return rsa.PrivateKey.load_pkcs1(f.read())
    except FileNotFoundError:
        raise RuntimeError(
            f"CloudFront private key file not found at: {path}. "
            "Mount it into the container (docker volume) or fix the path."
        )



def _rsa_signer(message: bytes) -> bytes:
    private_key = _load_cf_private_key_cached()
    return rsa.sign(message, private_key, "SHA-1")



def _build_custom_policy(resource_url: str, expire_epoch: int) -> str:
    """
    Build CloudFront custom policy allowing wildcard access
    to the FULL HLS directory (playlist + segments).
    """

    parsed = urlparse(resource_url)

    # Example path:
    # /posts/videos/moment/2026/01/17/<uuid>/playlist.m3u8
    path = parsed.path or ""

    if "/" not in path:
        resource_path = path
    else:
        # Remove the file name (playlist.m3u8)
        base_dir = path.rsplit("/", 1)[0]
        resource_path = f"{base_dir}/*"

    resource = f"{parsed.scheme}://{parsed.netloc}{resource_path}"

    policy = {
        "Statement": [
            {
                "Resource": resource,
                "Condition": {
                    "DateLessThan": {
                        "AWS:EpochTime": expire_epoch
                    }
                }
            }
        ]
    }

    return json.dumps(policy, separators=(",", ":"))


def build_signed_url(*, resource_url: str, expires_in: int) -> SignedResult:
    """
    Build CloudFront signed URL.

    Uses CUSTOM POLICY (required for HLS).
    """

    expires_in = int(expires_in)

    allow_unsigned = bool(getattr(settings, "ASSET_DELIVERY_ALLOW_UNSIGNED_IN_DEBUG", False))

    if settings.DEBUG and allow_unsigned:
        logger.warning("[AssetDelivery] DEBUG unsigned CDN URL")
        return SignedResult(url=resource_url, expires_in=expires_in)

    key_pair_id = getattr(settings, "CLOUDFRONT_KEY_PAIR_ID", "") or ""
    if not key_pair_id:
        raise RuntimeError("CLOUDFRONT_KEY_PAIR_ID is not set.")

    signer = CloudFrontSigner(key_pair_id, _rsa_signer)

    expire_epoch = int(time.time()) + expires_in

    # 🔐 Custom policy (HLS-safe)
    policy = _build_custom_policy(
        resource_url=resource_url,
        expire_epoch=expire_epoch,
    )

    signed_url = signer.generate_presigned_url(
        resource_url,
        policy=policy,
    )

    return SignedResult(url=signed_url, expires_in=expires_in)


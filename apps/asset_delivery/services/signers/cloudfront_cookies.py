# apps/asset_delivery/services/signers/cloudfront_cookies.py

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, parse_qs


@dataclass(frozen=True)
class SignedCookies:
    policy: str
    signature: str
    key_pair_id: str


def signed_url_to_cookies(signed_url: str) -> SignedCookies:
    # Extract signed URL query -> cookies
    qs = parse_qs(urlsplit(signed_url).query)

    policy = (qs.get("Policy") or [None])[0]
    signature = (qs.get("Signature") or [None])[0]
    key_pair_id = (qs.get("Key-Pair-Id") or [None])[0]

    if not policy or not signature or not key_pair_id:
        raise ValueError("Signed URL missing Policy/Signature/Key-Pair-Id")

    return SignedCookies(policy=policy, signature=signature, key_pair_id=key_pair_id)


def strip_query(url: str) -> str:
    # Return URL without query string
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"

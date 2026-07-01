# apps/core/square/projections/media.py

from __future__ import annotations

import boto3

from botocore.config import Config
from django.conf import settings

from apps.asset_delivery.services.job_resolver import get_latest_done_output_path
from apps.asset_delivery.services.playback_resolver import resolve_fallback_filefield_key


def clean_key(value) -> str | None:
    if not value:
        return None

    raw = getattr(value, "name", value)

    if not raw:
        return None

    cleaned = str(raw).strip().lstrip("/")
    return cleaned or None


def cdn_url(key: str | None) -> str | None:
    """
    Build the regular CDN-style URL.

    This is fine for public CDN media and for images that can still fall back
    through the existing resolver path. Do not use this for private MP4 preview
    playback consumed directly by AVPlayer.
    """

    key = clean_key(key)

    if not key:
        return None

    base = (getattr(settings, "ASSET_CDN_BASE_URL", "") or "").rstrip("/")

    if not base:
        return None

    return f"{base}/{key}"


def s3_presigned_url(
    key: str | None,
    *,
    content_type: str | None = None,
) -> str | None:
    """
    Return a presigned S3 URL for private media objects.

    Square video preview is consumed directly by AVPlayer, so it must be
    accessible without app auth headers.
    """

    key = clean_key(key)

    if not key:
        return None

    bucket_name = (
        getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
        or getattr(settings, "AWS_S3_BUCKET_NAME", None)
    )

    if not bucket_name:
        return None

    region_name = (
        getattr(settings, "AWS_S3_REGION_NAME", None)
        or getattr(settings, "AWS_REGION", None)
        or "us-east-1"
    )

    expires_in = int(
        getattr(settings, "SQUARE_VIDEO_PREVIEW_URL_TTL_SECONDS", 21600)
    )

    client_kwargs = {
        "region_name": region_name,
        "config": Config(signature_version="s3v4"),
    }

    access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None)
    secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
    session_token = getattr(settings, "AWS_SESSION_TOKEN", None)

    if access_key and secret_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key

    if session_token:
        client_kwargs["aws_session_token"] = session_token

    params = {
        "Bucket": bucket_name,
        "Key": key,
    }

    if content_type:
        params["ResponseContentType"] = content_type

    try:
        client = boto3.client(
            "s3",
            **client_kwargs,
        )

        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    except Exception:
        return None


def signed_video_preview_url(key: str | None) -> str | None:
    """
    Return an actually playable URL for private Square preview MP4.

    Do not return the raw CDN URL here. Private CloudFront/S3 returns 403 for
    AVPlayer unless the URL is signed.
    """

    key = clean_key(key)

    if not key:
        return None

    return s3_presigned_url(
        key,
        content_type="video/mp4",
    )


def media_asset(obj, field_name: str) -> dict:
    assets = getattr(obj, "media_assets", None) or {}

    if not isinstance(assets, dict):
        return {}

    value = assets.get(field_name)
    return value if isinstance(value, dict) else {}


def media_dimensions(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {
            "width": None,
            "height": None,
            "aspect_ratio": None,
        }

    return {
        "width": payload.get("width"),
        "height": payload.get("height"),
        "aspect_ratio": payload.get("aspect_ratio"),
    }


def variants_payload(variants: dict | None) -> dict:
    if not isinstance(variants, dict):
        return {}

    output = {}

    for name, payload in variants.items():
        if not isinstance(payload, dict):
            continue

        key = clean_key(payload.get("key"))
        url = cdn_url(key)

        output[name] = {
            **payload,
            "key": key,
            "cdn_url": url,
            "image_url": url,
            "url": url,
        }

    return output


def image_asset_payload(obj, field_name: str) -> dict:
    asset = media_asset(obj, field_name)
    key = clean_key(asset.get("key")) or safe_preview_key(obj, field_name)
    url = cdn_url(key)

    return {
        **asset,
        "key": key,
        "cdn_url": url,
        "image_url": url,
        "url": url,
        "variants": variants_payload(asset.get("variants")),
        **media_dimensions(asset),
    }


def video_preview_payload(obj, field_name: str = "video") -> dict | None:
    """
    Preview MP4 payload for Square/Profile autoplay.

    S3/CloudFront is private, so AVPlayer needs a presigned URL. Returning the
    raw media.townlit.com URL causes 403 and the Square card stays on poster.
    """

    asset = media_asset(obj, field_name)
    preview = asset.get("preview")

    if not isinstance(preview, dict):
        return None

    key = clean_key(preview.get("key"))

    if not key:
        return None

    url = signed_video_preview_url(key)

    if not url:
        return None

    return {
        **preview,
        "key": key,
        "cdn_url": url,
        "video_url": url,
        "url": url,
    }


def video_qualities_payload(obj, field_name: str = "video") -> list:
    asset = media_asset(obj, field_name)
    qualities = asset.get("qualities")

    return qualities if isinstance(qualities, list) else []


def safe_preview_key(obj, field_name: str):
    """
    Safe preview resolver for feed usage.
    NEVER raises exception.
    NEVER requires conversion.
    """

    asset_key = clean_key(media_asset(obj, field_name).get("key"))

    if asset_key:
        return asset_key

    try:
        key = get_latest_done_output_path(
            target_obj=obj,
            field_name=field_name,
            kind="image",
        )
        if key:
            return clean_key(key)
    except Exception:
        pass

    try:
        key = resolve_fallback_filefield_key(obj, field_name)
        if key:
            return clean_key(key)
    except Exception:
        pass

    return None
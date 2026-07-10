# apps/core/streams/preview.py

from typing import Optional

from django.conf import settings
import boto3
from botocore.config import Config
from functools import lru_cache

from apps.asset_delivery.services.job_resolver import get_latest_done_output_path
from apps.asset_delivery.services.playback_resolver import resolve_fallback_filefield_key


def _cdn_url(key: str | None) -> str | None:
    """
    Build clean CDN URL.
    """

    if not key:
        return None

    base = (getattr(settings, "ASSET_CDN_BASE_URL", "") or "").rstrip("/")
    if not base:
        return None

    return f"{base}/{str(key).lstrip('/')}"


@lru_cache(maxsize=8)
def _cached_s3_client(
    *,
    region_name: str,
    access_key: str | None,
    secret_key: str | None,
    session_token: str | None,
):
    client_kwargs = {
        "region_name": region_name,
        "config": Config(signature_version="s3v4"),
    }

    if access_key and secret_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key

    if session_token:
        client_kwargs["aws_session_token"] = session_token

    return boto3.client(
        "s3",
        **client_kwargs,
    )

def _s3_presigned_url(
    key: str | None,
    *,
    content_type: str | None = None,
) -> str | None:
    """
    Return a presigned S3 URL for private media objects.
    """

    key = _clean_key(key)

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
        getattr(settings, "STREAM_VIDEO_PREVIEW_URL_TTL_SECONDS", 21600)
    )

    params = {
        "Bucket": bucket_name,
        "Key": key,
    }

    if content_type:
        params["ResponseContentType"] = content_type

    try:
        access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None)
        secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
        session_token = getattr(settings, "AWS_SESSION_TOKEN", None)

        client = _cached_s3_client(
            region_name=region_name,
            access_key=access_key,
            secret_key=secret_key,
            session_token=session_token,
        )

        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    except Exception:
        return None


def _signed_video_preview_url(key: str | None) -> str | None:
    """
    Return playable URL for private short preview MP4.
    """

    key = _clean_key(key)

    if not key:
        return None

    return _s3_presigned_url(
        key,
        content_type="video/mp4",
    )

def _clean_key(value) -> str | None:
    """
    Normalize storage key-like values.
    """

    if not value:
        return None

    raw = getattr(value, "name", value)

    if not raw:
        return None

    cleaned = str(raw).strip().lstrip("/")
    return cleaned or None


def _positive_int(value) -> int | None:
    """
    Normalize positive integer values.
    """

    try:
        parsed = int(value)
    except Exception:
        return None

    return parsed if parsed > 0 else None


def _positive_float(value) -> float | None:
    """
    Normalize positive float values.
    """

    try:
        parsed = float(value)
    except Exception:
        return None

    return parsed if parsed > 0 else None


def _aspect_ratio_payload(
    *,
    width=None,
    height=None,
    aspect_ratio=None,
) -> dict:
    """
    Build safe media dimension metadata.
    """

    normalized_width = _positive_int(width)
    normalized_height = _positive_int(height)
    normalized_ratio = _positive_float(aspect_ratio)

    if not normalized_ratio and normalized_width and normalized_height:
        normalized_ratio = normalized_width / normalized_height

    return {
        "width": normalized_width,
        "height": normalized_height,
        "aspect_ratio": normalized_ratio,
    }


def _media_asset(obj, field_name: str) -> dict:
    """
    Read stored media asset metadata.
    """

    assets = getattr(obj, "media_assets", None) or {}

    if not isinstance(assets, dict):
        return {}

    value = assets.get(field_name)
    return value if isinstance(value, dict) else {}


def _asset_dimensions(asset: dict) -> dict:
    """
    Extract dimension metadata from a stored asset.
    """

    if not isinstance(asset, dict):
        return _aspect_ratio_payload()

    return _aspect_ratio_payload(
        width=asset.get("width"),
        height=asset.get("height"),
        aspect_ratio=asset.get("aspect_ratio"),
    )


def _model_dimension_payload(obj, field_name: str) -> dict:
    """
    Resolve dimensions from explicit model metadata only.

    Important:
    This function must not open media files or touch remote storage.
    Stream endpoints should stay fast.
    """

    asset_payload = _asset_dimensions(
        _media_asset(obj, field_name)
    )

    if asset_payload.get("aspect_ratio"):
        return asset_payload

    candidate_prefixes = [
        field_name,
        "media",
        "preview",
        "thumbnail" if field_name == "thumbnail" else field_name,
    ]

    for prefix in candidate_prefixes:
        width = (
            getattr(obj, f"{prefix}_width", None)
            or getattr(obj, f"{prefix}_w", None)
        )
        height = (
            getattr(obj, f"{prefix}_height", None)
            or getattr(obj, f"{prefix}_h", None)
        )
        aspect_ratio = (
            getattr(obj, f"{prefix}_aspect_ratio", None)
            or getattr(obj, f"{prefix}_ratio", None)
        )

        payload = _aspect_ratio_payload(
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
        )

        if payload["aspect_ratio"]:
            return payload

    return _aspect_ratio_payload()


def _json_image_item_dimensions(item: dict) -> dict:
    """
    Resolve dimensions from JSON-backed Moment image item metadata.
    """

    if not isinstance(item, dict):
        return _aspect_ratio_payload()

    return _aspect_ratio_payload(
        width=item.get("width"),
        height=item.get("height"),
        aspect_ratio=item.get("aspect_ratio"),
    )


def _safe_preview_key(obj, field_name: str) -> Optional[str]:
    """
    Resolve preview key safely.

    Used for normal FileField/ImageField media such as:
    - image
    - thumbnail
    """

    asset_key = _clean_key(
        _media_asset(obj, field_name).get("key")
    )

    if asset_key:
        return asset_key

    try:
        key = get_latest_done_output_path(
            target_obj=obj,
            field_name=field_name,
            kind="image",
        )
        if key:
            return _clean_key(key)
    except Exception:
        pass

    try:
        key = resolve_fallback_filefield_key(obj, field_name)
        if key:
            return _clean_key(key)
    except Exception:
        pass

    return None


def _is_moment_like(obj) -> bool:
    """
    Detect Moment-like object without importing Moment here.
    """

    return (
        hasattr(obj, "image_items")
        or hasattr(obj, "cover_image_id")
        or hasattr(obj, "cover_image_key")
    )


def _ordered_image_items(obj) -> list[dict]:
    """
    Return valid ordered JSON-backed image items.
    """

    try:
        if hasattr(obj, "normalized_image_items"):
            items = obj.normalized_image_items()
        else:
            items = getattr(obj, "image_items", None) or []

        if not isinstance(items, list):
            return []

        cleaned = [
            item
            for item in items
            if isinstance(item, dict)
            and item.get("id")
            and item.get("key")
        ]

        return sorted(
            cleaned,
            key=lambda item: int(item.get("order", 0) or 0),
        )

    except Exception:
        return []


def _cover_image_key(obj) -> str | None:
    """
    Resolve pinned/primary Moment photo key.
    """

    try:
        if hasattr(obj, "cover_image_key"):
            key = obj.cover_image_key()
            if key:
                return _clean_key(key)

        items = _ordered_image_items(obj)
        if not items:
            return None

        cover_id = str(getattr(obj, "cover_image_id", "") or "")

        if cover_id:
            for item in items:
                if str(item.get("id")) == cover_id:
                    key = _clean_key(item.get("key"))
                    return key or None

        key = _clean_key(items[0].get("key"))
        return key or None

    except Exception:
        return None


def _variant_url_payload(variants: dict | None) -> dict:
    """
    Add CDN URLs to stored image variants.
    """

    if not isinstance(variants, dict):
        return {}

    output = {}

    for name, payload in variants.items():
        if not isinstance(payload, dict):
            continue

        key = _clean_key(payload.get("key"))
        url = _cdn_url(key)

        output[name] = {
            **payload,
            "key": key,
            "cdn_url": url,
            "image_url": url,
        }

    return output


def _video_preview_payload(payload: dict | None) -> dict | None:
    """
    Add playable URL to stored short video preview.
    """

    if not isinstance(payload, dict):
        return None

    key = _clean_key(payload.get("key"))

    if not key:
        return None

    url = _signed_video_preview_url(key)

    if not url:
        return None

    return {
        **payload,
        "key": key,
        "cdn_url": url,
        "video_url": url,
        "url": url,
    }


def _image_asset_payload(asset: dict | None) -> dict:
    """
    Add CDN URLs and variants to an image asset.
    """

    if not isinstance(asset, dict):
        return {}

    key = _clean_key(asset.get("key"))
    url = _cdn_url(key)

    return {
        **asset,
        "key": key,
        "cdn_url": url,
        "image_url": url,
        "variants": _variant_url_payload(
            asset.get("variants")
        ),
    }


def _image_items_payload(obj) -> list[dict]:
    """
    Build lightweight image item metadata for Stream clients.

    Important:
    - field_name is used by asset-delivery resolving/warmup.
    - cdn_url/image_url are used by web/iOS as direct safe preview sources.
    - width/height/aspect_ratio let iOS render media at its real ratio.
    - variants let clients pick the right size without runtime resizing.
    """

    items = _ordered_image_items(obj)
    cover_id = str(getattr(obj, "cover_image_id", "") or "")

    payload = []

    for index, item in enumerate(items):
        item_id = str(item.get("id") or "").strip()
        key = _clean_key(item.get("key"))

        if not item_id or not key:
            continue

        url = _cdn_url(key)
        dimensions = _json_image_item_dimensions(item)
        variants = _variant_url_payload(
            item.get("variants")
            if isinstance(item.get("variants"), dict)
            else {}
        )

        payload.append(
            {
                "id": item_id,
                "key": key,
                "order": int(item.get("order", index) or index),
                "file_name": item.get("file_name") or key.split("/")[-1],
                "mime_type": item.get("mime_type") or "",
                "size": int(item.get("size") or 0),
                "is_cover": item_id == cover_id or bool(item.get("is_cover")),
                "field_name": f"image_items:{item_id}",

                # Layout metadata.
                "width": dimensions["width"],
                "height": dimensions["height"],
                "aspect_ratio": dimensions["aspect_ratio"],

                # Image variants.
                "variants": variants,

                # Direct preview URLs.
                "cdn_url": url,
                "image_url": url,
            }
        )

    return payload


def _cover_image_payload(obj, image_items: list[dict]) -> dict | None:
    """
    Build cover descriptor for Stream clients.
    """

    if not image_items:
        if getattr(obj, "image", None):
            image_asset = _image_asset_payload(
                _media_asset(obj, "image")
            )

            key = (
                _clean_key(image_asset.get("key"))
                or _safe_preview_key(obj, "image")
            )

            url = _cdn_url(key)

            dimensions = _asset_dimensions(image_asset)

            if not dimensions.get("aspect_ratio"):
                dimensions = _model_dimension_payload(obj, "image")

            return {
                "id": None,
                "field_name": "image",
                "source": "image",
                "key": key,
                "cdn_url": url,
                "image_url": url,
                "width": dimensions["width"],
                "height": dimensions["height"],
                "aspect_ratio": dimensions["aspect_ratio"],
                "variants": image_asset.get("variants") or {},
            }

        return None

    cover_id = str(getattr(obj, "cover_image_id", "") or "")

    if cover_id:
        for item in image_items:
            if str(item.get("id")) == cover_id:
                return {
                    "id": item["id"],
                    "field_name": item["field_name"],
                    "source": "image_items",
                    "key": item.get("key"),
                    "cdn_url": item.get("cdn_url"),
                    "image_url": item.get("image_url"),
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "aspect_ratio": item.get("aspect_ratio"),
                    "variants": item.get("variants") or {},
                }

    first = image_items[0]

    return {
        "id": first["id"],
        "field_name": first["field_name"],
        "source": "image_items",
        "key": first.get("key"),
        "cdn_url": first.get("cdn_url"),
        "image_url": first.get("image_url"),
        "width": first.get("width"),
        "height": first.get("height"),
        "aspect_ratio": first.get("aspect_ratio"),
        "variants": first.get("variants") or {},
    }


def _attach_moment_photo_metadata(out: dict, obj) -> dict:
    """
    Attach multi-photo Moment metadata to preview payload.
    """

    image_items = _image_items_payload(obj)
    cover_image = _cover_image_payload(obj, image_items)

    out["image_items"] = image_items
    out["cover_image_id"] = getattr(obj, "cover_image_id", None)
    out["cover_image"] = cover_image

    return out


def _apply_dimensions(
    out: dict,
    dimensions: dict,
) -> None:
    """
    Apply dimension metadata to preview payload.
    """

    out["width"] = dimensions.get("width")
    out["height"] = dimensions.get("height")
    out["aspect_ratio"] = dimensions.get("aspect_ratio")


def _apply_image_variants(
    out: dict,
    asset: dict,
) -> None:
    """
    Attach image variants to preview payload.
    """

    variants = asset.get("variants") if isinstance(asset, dict) else None
    out["variants"] = _variant_url_payload(variants)


def _quality_dimensions_payload(qualities: list | None) -> dict:
    """
    Resolve video dimensions from stored HLS quality metadata.

    Important:
    This is video metadata, unlike thumbnail/poster metadata.
    """

    if not isinstance(qualities, list):
        return _aspect_ratio_payload()

    for quality in qualities:
        if not isinstance(quality, dict):
            continue

        if quality.get("key") == "source":
            dimensions = _aspect_ratio_payload(
                width=quality.get("width"),
                height=quality.get("height"),
                aspect_ratio=quality.get("aspect_ratio"),
            )

            if dimensions.get("aspect_ratio"):
                return dimensions

    for quality in qualities:
        if not isinstance(quality, dict):
            continue

        dimensions = _aspect_ratio_payload(
            width=quality.get("width"),
            height=quality.get("height"),
            aspect_ratio=quality.get("aspect_ratio"),
        )

        if dimensions.get("aspect_ratio"):
            return dimensions

    return _aspect_ratio_payload()


def _safe_video_layout_fallback() -> dict:
    """
    Safe fallback for old video rows that are not backfilled yet.

    Do not use thumbnail dimensions for video layout. A thumbnail can be very
    wide and create a short collapsed card.
    """

    return {
        "width": None,
        "height": None,
        "aspect_ratio": 9 / 16,
    }


def _apply_video_asset_metadata(
    out: dict,
    obj,
) -> None:
    """
    Attach stored video metadata and short preview.

    Critical rule:
    Video layout dimensions must come from video metadata only:
    - media_assets.video.width/height/aspect_ratio
    - media_assets.video.qualities[*].width/height/aspect_ratio

    Never use thumbnail/poster dimensions for video layout.
    """

    video_asset = _media_asset(obj, "video")
    qualities = (
        video_asset.get("qualities")
        if isinstance(video_asset.get("qualities"), list)
        else []
    )

    dimensions = _asset_dimensions(video_asset)

    if not dimensions.get("aspect_ratio"):
        dimensions = _quality_dimensions_payload(qualities)

    if not dimensions.get("aspect_ratio"):
        dimensions = _safe_video_layout_fallback()

    _apply_dimensions(out, dimensions)

    out["duration_ms"] = video_asset.get("duration_ms")
    out["preview_video"] = _video_preview_payload(
        video_asset.get("preview")
    )
    out["video_qualities"] = qualities


def _build_empty_preview() -> dict:
    """
    Build default preview shape.
    """

    return {
        "thumbnail_url": None,
        "image_url": None,
        "poster_url": None,
        "type": None,
        "has_video": False,

        # Layout metadata for iOS/web stream rendering.
        "width": None,
        "height": None,
        "aspect_ratio": None,
        "duration_ms": None,

        # Stored responsive assets.
        "variants": {},
        "preview_video": None,
        "video_qualities": [],

        # Multi-photo Moment fields.
        "image_items": [],
        "cover_image_id": None,
        "cover_image": None,
    }


def build_stream_preview(obj, *, subtype: str) -> dict:
    """
    Build frontend-safe preview payload.
    """

    out = _build_empty_preview()

    # Testimony-like object.
    if hasattr(obj, "type"):
        out["type"] = getattr(obj, "type", None)

        if subtype == "written":
            return out

        if subtype == "audio":
            artwork_key = _safe_preview_key(obj, "audio_artwork")
            thumbnail_key = _safe_preview_key(obj, "thumbnail")

            artwork_url = _cdn_url(artwork_key)
            thumbnail_url = _cdn_url(thumbnail_key)

            out["thumbnail_url"] = thumbnail_url
            out["image_url"] = artwork_url
            out["poster_url"] = artwork_url or thumbnail_url

            artwork_asset = _media_asset(obj, "audio_artwork")
            thumbnail_asset = _media_asset(obj, "thumbnail")

            dimensions = _asset_dimensions(artwork_asset)

            if not dimensions.get("aspect_ratio"):
                dimensions = _asset_dimensions(thumbnail_asset)

            if not dimensions.get("aspect_ratio"):
                dimensions = _model_dimension_payload(obj, "audio_artwork")

            _apply_dimensions(out, dimensions)
            _apply_image_variants(out, artwork_asset or thumbnail_asset)

            return out

        thumb_key = _safe_preview_key(obj, "thumbnail")
        image_key = _safe_preview_key(obj, "image")

        thumbnail_url = _cdn_url(thumb_key)
        image_url = _cdn_url(image_key)

        out["thumbnail_url"] = thumbnail_url
        out["image_url"] = image_url
        out["poster_url"] = thumbnail_url or image_url

        if subtype == "video":
            out["has_video"] = True
            _apply_video_asset_metadata(out, obj)
            return out

        thumbnail_asset = _media_asset(obj, "thumbnail")
        image_asset = _media_asset(obj, "image")

        dimensions = _asset_dimensions(thumbnail_asset)

        if not dimensions.get("aspect_ratio"):
            dimensions = _asset_dimensions(image_asset)

        if not dimensions.get("aspect_ratio"):
            dimensions = _model_dimension_payload(obj, "thumbnail")

        _apply_dimensions(out, dimensions)
        _apply_image_variants(out, thumbnail_asset or image_asset)

        return out

    # Video object.
    if subtype == "video":
        thumb_key = _safe_preview_key(obj, "thumbnail")
        image_key = _safe_preview_key(obj, "image")

        thumbnail_url = _cdn_url(thumb_key)
        image_url = _cdn_url(image_key)

        out["type"] = "video"
        out["has_video"] = True
        out["thumbnail_url"] = thumbnail_url
        out["image_url"] = image_url
        out["poster_url"] = thumbnail_url or image_url

        _apply_video_asset_metadata(out, obj)

        return out

    # Image object.
    if subtype == "image":
        if _is_moment_like(obj):
            cover_key = _cover_image_key(obj)
            image_key = cover_key or _safe_preview_key(obj, "image")
            thumb_key = None
        else:
            image_key = _safe_preview_key(obj, "image")
            thumb_key = _safe_preview_key(obj, "thumbnail")

        image_url = _cdn_url(image_key)
        thumbnail_url = _cdn_url(thumb_key)

        out["type"] = "image"
        out["image_url"] = image_url
        out["thumbnail_url"] = thumbnail_url
        out["poster_url"] = image_url or thumbnail_url

        if _is_moment_like(obj):
            out = _attach_moment_photo_metadata(out, obj)

            # Keep cover URL and dimensions aligned with selected cover item.
            cover_image = out.get("cover_image") or {}
            cover_url = cover_image.get("cdn_url") or cover_image.get("image_url")

            if cover_url:
                out["image_url"] = cover_url
                out["poster_url"] = cover_url

            out["width"] = cover_image.get("width")
            out["height"] = cover_image.get("height")
            out["aspect_ratio"] = cover_image.get("aspect_ratio")
            out["variants"] = cover_image.get("variants") or {}

            # Legacy Moment image fallback.
            if not out["aspect_ratio"]:
                image_asset = _media_asset(obj, "image")
                dimensions = _asset_dimensions(image_asset)

                if not dimensions.get("aspect_ratio"):
                    dimensions = _model_dimension_payload(obj, "image")

                _apply_dimensions(out, dimensions)
                _apply_image_variants(out, image_asset)

        else:
            image_asset = _media_asset(obj, "image")
            thumbnail_asset = _media_asset(obj, "thumbnail")

            dimensions = _asset_dimensions(image_asset)

            if not dimensions.get("aspect_ratio"):
                dimensions = _asset_dimensions(thumbnail_asset)

            if not dimensions.get("aspect_ratio"):
                dimensions = _model_dimension_payload(obj, "image")

            _apply_dimensions(out, dimensions)
            _apply_image_variants(out, image_asset)

        return out

    return out
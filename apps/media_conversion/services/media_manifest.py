# apps/media_conversion/services/media_manifest.py

from __future__ import annotations


def clean_payload(payload: dict) -> dict:
    return {
        key: value
        for key, value in (payload or {}).items()
        if value is not None
    }


def build_asset_payload(
    *,
    key: str,
    metadata: dict,
    variants: dict | None = None,
    extra: dict | None = None,
) -> dict:
    payload = {
        "key": str(key).lstrip("/"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "aspect_ratio": metadata.get("aspect_ratio"),
        "duration_ms": metadata.get("duration_ms"),
        "mime_type": metadata.get("mime_type"),
        "size": metadata.get("size"),
    }

    if variants:
        payload["variants"] = variants

    if extra:
        payload.update(extra)

    return clean_payload(payload)


def update_instance_media_asset(
    *,
    instance,
    field_name: str,
    payload: dict,
) -> None:
    """
    Store media asset metadata on the target model.
    """

    if not hasattr(instance, "media_assets"):
        return

    assets = dict(getattr(instance, "media_assets", None) or {})
    assets[field_name] = payload or {}

    type(instance)._base_manager.filter(pk=instance.pk).update(
        media_assets=assets,
    )
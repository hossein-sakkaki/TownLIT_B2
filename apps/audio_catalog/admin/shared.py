# apps/audio_catalog/admin/shared.py

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobStatus,
)


logger = logging.getLogger(__name__)

ADMIN_PRIVATE_URL_EXPIRES_SECONDS = 15 * 60


def admin_change_url(
    instance,
) -> str:
    """
    Build an admin change URL only when the model is registered.
    """

    if (
        instance is None
        or not getattr(instance, "pk", None)
    ):
        return ""

    model_class = instance.__class__

    if model_class not in admin.site._registry:
        return ""

    try:
        return reverse(
            (
                f"admin:"
                f"{instance._meta.app_label}_"
                f"{instance._meta.model_name}_change"
            ),
            args=[
                instance.pk,
            ],
        )
    except NoReverseMatch:
        return ""


def admin_add_url(
    *,
    app_label: str,
    model_name: str,
    query: str = "",
) -> str:
    """
    Build an admin add URL safely.
    """

    try:
        url = reverse(
            f"admin:{app_label}_{model_name}_add"
        )
    except NoReverseMatch:
        return ""

    if query:
        return f"{url}?{query}"

    return url


def linked_object(
    instance,
    *,
    label: str | None = None,
) -> str:
    """
    Render an admin object link when available.
    """

    if (
        instance is None
        or not getattr(instance, "pk", None)
    ):
        return "—"

    text = (
        label
        or str(instance)
    )

    url = admin_change_url(
        instance
    )

    if not url:
        return format_html(
            "{}",
            text,
        )

    return format_html(
        '<a href="{}">{}</a>',
        url,
        text,
    )


def _storage_name(
    field_file,
) -> str:
    """
    Return a normalized storage object name.
    """

    return (
        getattr(
            field_file,
            "name",
            "",
        )
        or ""
    ).strip()


def _storage_exists(
    *,
    storage,
    name: str,
) -> bool:
    """
    Check whether the object exists without breaking the admin.
    """

    try:
        return bool(
            storage.exists(
                name
            )
        )
    except Exception:
        # URL generation may still work on some storages.
        return True


def _generate_storage_presigned_url(
    *,
    storage,
    name: str,
    expires: int,
    download_name: str = "",
) -> str:
    """
    Generate a signed S3 URL directly.

    This bypasses AWS_S3_CUSTOM_DOMAIN because a custom domain may
    return an unsigned URL for a private bucket.
    """

    bucket_name = (
        getattr(
            storage,
            "bucket_name",
            "",
        )
        or ""
    ).strip()

    if not bucket_name:
        bucket = getattr(
            storage,
            "bucket",
            None,
        )

        bucket_name = (
            getattr(
                bucket,
                "name",
                "",
            )
            or ""
        ).strip()

    if not bucket_name:
        return ""

    try:
        connection = getattr(
            storage,
            "connection",
            None,
        )

        client = getattr(
            getattr(
                connection,
                "meta",
                None,
            ),
            "client",
            None,
        )

        if client is None:
            return ""

        params = {
            "Bucket": bucket_name,
            "Key": name,
        }

        if download_name:
            safe_name = quote(
                download_name,
                safe="._- ",
            )

            params[
                "ResponseContentDisposition"
            ] = (
                f'attachment; filename="{safe_name}"'
            )
        else:
            params[
                "ResponseContentDisposition"
            ] = "inline"

        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=max(
                60,
                int(expires),
            ),
        )

    except Exception:
        logger.exception(
            "Failed to generate private admin media URL",
            extra={
                "storage_name": name,
                "bucket_name": bucket_name,
            },
        )

        return ""


def _generate_native_storage_url(
    *,
    storage,
    name: str,
    expires: int,
) -> str:
    """
    Try the storage backend's own signing interface.
    """

    attempts = (
        {
            "expire": expires,
        },
        {
            "parameters": {
                "ResponseContentDisposition": "inline",
            },
            "expire": expires,
        },
        {},
    )

    for kwargs in attempts:
        try:
            url = storage.url(
                name,
                **kwargs,
            )
        except TypeError:
            continue
        except Exception:
            return ""

        if url:
            return str(url)

    return ""


def safe_file_url(
    field_file,
    *,
    expires: int = ADMIN_PRIVATE_URL_EXPIRES_SECONDS,
) -> str:
    """
    Resolve a private temporary media URL safely.

    Priority:
    1. Direct S3 presigned URL.
    2. Storage backend URL generation.
    3. Empty result when neither is available.

    Direct S3 signing is tried first because django-storages may
    return an unsigned AWS_S3_CUSTOM_DOMAIN URL for private files.
    """

    if not field_file:
        return ""

    name = _storage_name(
        field_file
    )

    storage = getattr(
        field_file,
        "storage",
        None,
    )

    if (
        not name
        or storage is None
    ):
        return ""

    if not _storage_exists(
        storage=storage,
        name=name,
    ):
        return ""

    signed_url = (
        _generate_storage_presigned_url(
            storage=storage,
            name=name,
            expires=expires,
        )
    )

    if signed_url:
        return signed_url

    return _generate_native_storage_url(
        storage=storage,
        name=name,
        expires=expires,
    )


def render_image_preview(
    field_file,
    *,
    width: int = 96,
    height: int = 96,
) -> str:
    """
    Render a private image preview.
    """

    url = safe_file_url(
        field_file
    )

    if not url:
        return format_html(
            '<span style="color:#888;">{}</span>',
            "Preview unavailable",
        )

    return format_html(
        (
            '<a href="{url}" '
            'target="_blank" '
            'rel="noopener noreferrer">'
            '<img '
            'src="{url}" '
            'alt="Artwork preview" '
            'loading="lazy" '
            'style="'
            'display:block;'
            'width:{width}px;'
            'height:{height}px;'
            'object-fit:cover;'
            'border-radius:12px;'
            'border:1px solid #d7d7d7;'
            'background:#f5f5f5;'
            '" />'
            "</a>"
        ),
        url=url,
        width=max(
            1,
            int(width),
        ),
        height=max(
            1,
            int(height),
        ),
    )


def render_audio_player(
    field_file,
    *,
    width: int = 320,
) -> str:
    """
    Render a private signed audio player.
    """

    url = safe_file_url(
        field_file
    )

    if not url:
        return format_html(
            '<span style="color:#888;">{}</span>',
            "Audio preview unavailable",
        )

    resolved_width = max(
        180,
        int(width),
    )

    return format_html(
        (
            '<div style="'
            'min-width:{width}px;'
            'max-width:100%;'
            '">'
            '<audio '
            'controls '
            'preload="metadata" '
            'controlslist="nodownload" '
            'style="'
            'display:block;'
            'width:{width}px;'
            'max-width:100%;'
            '">'
            '<source src="{url}">'
            "Your browser does not support audio playback."
            "</audio>"
            '<div style="margin-top:5px;">'
            '<a href="{url}" '
            'target="_blank" '
            'rel="noopener noreferrer">'
            "Open audio preview"
            "</a>"
            "</div>"
            "</div>"
        ),
        url=url,
        width=resolved_width,
    )


def render_file_link(
    field_file,
    *,
    label: str = "Open file",
) -> str:
    """
    Render a private signed file link.
    """

    url = safe_file_url(
        field_file
    )

    if not url:
        return format_html(
            '<span style="color:#888;">{}</span>',
            "File unavailable",
        )

    return format_html(
        (
            '<a href="{}" '
            'target="_blank" '
            'rel="noopener noreferrer">'
            "{}"
            "</a>"
        ),
        url,
        label,
    )


def render_json(
    value: Any,
) -> str:
    """
    Render JSON as formatted admin content.
    """

    if not value:
        return "—"

    try:
        content = json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        content = str(
            value
        )

    return format_html(
        (
            '<pre style="'
            'max-width:900px;'
            'max-height:420px;'
            'overflow:auto;'
            'white-space:pre-wrap;'
            'overflow-wrap:anywhere;'
            'padding:12px;'
            'border:1px solid #ddd;'
            'border-radius:8px;'
            'background:#f7f7f7;'
            '">{}</pre>'
        ),
        content,
    )


def status_badge(
    label: str,
    *,
    background: str,
    foreground: str = "#ffffff",
) -> str:
    """
    Render a compact status badge.
    """

    return format_html(
        (
            '<span style="'
            'display:inline-block;'
            'padding:3px 8px;'
            'border-radius:999px;'
            'font-size:11px;'
            'font-weight:700;'
            'line-height:1.4;'
            'background:{};'
            'color:{};'
            '">{}</span>'
        ),
        background,
        foreground,
        label,
    )


def conversion_status_badge(
    instance,
) -> str:
    """
    Render conversion readiness.
    """

    if getattr(
        instance,
        "is_converted",
        False,
    ):
        return status_badge(
            "Ready",
            background="#18864b",
        )

    return status_badge(
        "Pending",
        background="#c57a00",
    )


def latest_conversion_job(
    instance,
):
    """
    Return the latest conversion job.
    """

    if (
        instance is None
        or not getattr(
            instance,
            "pk",
            None,
        )
    ):
        return None

    content_type = (
        ContentType.objects
        .get_for_model(
            instance,
            for_concrete_model=False,
        )
    )

    return (
        MediaConversionJob.objects
        .filter(
            content_type=content_type,
            object_id=instance.pk,
        )
        .order_by(
            "-created_at",
            "-id",
        )
        .first()
    )


def render_conversion_job(
    instance,
) -> str:
    """
    Render the latest conversion job.

    The badge remains visible even when MediaConversionJob is not
    registered in Django Admin.
    """

    job = latest_conversion_job(
        instance
    )

    if job is None:
        return format_html(
            '<span style="color:#777;">{}</span>',
            "No conversion job",
        )

    color_map = {
        MediaJobStatus.QUEUED: "#5c6ac4",
        MediaJobStatus.PROCESSING: "#0b76b7",
        MediaJobStatus.DONE: "#18864b",
        MediaJobStatus.FAILED: "#c0392b",
        MediaJobStatus.CANCELED: "#666666",
    }

    color = color_map.get(
        job.status,
        "#666666",
    )

    label = format_html(
        (
            '<span style="'
            'display:inline-block;'
            'padding:3px 8px;'
            'border-radius:999px;'
            'font-size:11px;'
            'font-weight:700;'
            'line-height:1.4;'
            'background:{};'
            'color:#fff;'
            '">'
            "{} · {}%"
            "</span>"
        ),
        color,
        job.status,
        job.progress or 0,
    )

    url = admin_change_url(
        job
    )

    if not url:
        return label

    return format_html(
        '<a href="{}">{}</a>',
        url,
        label,
    )


class LargeResultAdminMixin:
    """
    Shared defaults for large admin tables.
    """

    list_per_page = 50
    list_max_show_all = 200
    save_on_top = True
    preserve_filters = True
    show_full_result_count = False
    empty_value_display = "—"
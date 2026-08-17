# apps/creative_editor/admin/base.py

from __future__ import annotations

import logging
from typing import Any

from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString


logger = logging.getLogger(__name__)


ADMIN_PRIVATE_URL_EXPIRES_SECONDS = 15 * 60


class CreativeAdminStateActionsMixin:
    """
    Shared activate/deactivate actions.
    """

    @admin.action(
        description="Activate selected items",
    )
    def activate_selected(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        updated = queryset.update(
            is_active=True,
        )

        self.message_user(
            request,
            f"{updated} item(s) activated.",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Deactivate selected items",
    )
    def deactivate_selected(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        updated = queryset.update(
            is_active=False,
        )

        self.message_user(
            request,
            f"{updated} item(s) deactivated.",
            level=messages.WARNING,
        )


class CreativeAdminFeatureActionsMixin:
    """
    Shared featured/unfeatured actions.
    """

    @admin.action(
        description="Mark selected items as featured",
    )
    def feature_selected(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        updated = queryset.update(
            is_featured=True,
        )

        self.message_user(
            request,
            f"{updated} item(s) marked as featured.",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Remove selected items from featured",
    )
    def unfeature_selected(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        updated = queryset.update(
            is_featured=False,
        )

        self.message_user(
            request,
            f"{updated} item(s) removed from featured.",
            level=messages.INFO,
        )


def _storage_name(
    field_file,
) -> str:
    """
    Return a normalized storage object key.
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
    Check whether a storage object exists without breaking Admin.

    Some remote storage backends may fail an exists() call while
    still being able to generate a valid URL, so failures are treated
    as inconclusive rather than as a missing file.
    """

    try:
        return bool(
            storage.exists(
                name
            )
        )
    except Exception:
        return True


def _generate_storage_presigned_url(
    *,
    storage,
    name: str,
    expires: int,
) -> str:
    """
    Generate a private S3 presigned URL directly.

    This intentionally bypasses AWS_S3_CUSTOM_DOMAIN because a
    private bucket combined with a custom domain may otherwise
    produce an unsigned URL that the browser cannot load.
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

        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": bucket_name,
                "Key": name,
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=max(
                60,
                int(expires),
            ),
        )

    except Exception:
        logger.exception(
            "creative_editor.admin_private_media_url.failed",
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
    Fall back to the storage backend's URL generation interface.
    """

    attempts = (
        {
            "parameters": {
                "ResponseContentDisposition": "inline",
            },
            "expire": expires,
        },
        {
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


def admin_private_file_url(
    field_file,
    *,
    expires: int = ADMIN_PRIVATE_URL_EXPIRES_SECONDS,
) -> str:
    """
    Resolve a temporary private media URL for Django Admin.

    Resolution order:
    1. Direct S3 presigned URL.
    2. Native storage URL generation.
    3. Empty string when no URL can be generated.

    Direct S3 signing is intentionally preferred because
    django-storages may return an unsigned AWS_S3_CUSTOM_DOMAIN URL
    for objects stored in a private bucket.
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

    signed_url = _generate_storage_presigned_url(
        storage=storage,
        name=name,
        expires=expires,
    )

    if signed_url:
        return signed_url

    return _generate_native_storage_url(
        storage=storage,
        name=name,
        expires=expires,
    )


def admin_image_preview(
    *,
    image_field,
    width: int,
    height: int,
    border_radius: int = 12,
    background: str = "#f4f4f4",
    object_fit: str = "contain",
) -> SafeString | str:
    """
    Render an Admin image preview using a private temporary URL.
    """

    if not image_field:
        return "—"

    image_url = admin_private_file_url(
        image_field
    )

    if not image_url:
        return format_html(
            (
                '<span style="'
                'color:#888;'
                'font-size:12px;'
                '">'
                "{}"
                "</span>"
            ),
            "Preview unavailable",
        )

    resolved_width = max(
        1,
        int(width),
    )

    resolved_height = max(
        1,
        int(height),
    )

    resolved_radius = max(
        0,
        int(border_radius),
    )

    return format_html(
        (
            '<a href="{url}" '
            'target="_blank" '
            'rel="noopener noreferrer">'
            '<img '
            'src="{url}" '
            'alt="Creative asset preview" '
            'loading="lazy" '
            'style="'
            'display:block;'
            'width:{width}px;'
            'height:{height}px;'
            'object-fit:{object_fit};'
            'border-radius:{border_radius}px;'
            'background:{background};'
            'padding:5px;'
            'box-sizing:border-box;'
            'border:1px solid rgba(0,0,0,.10);'
            'box-shadow:0 4px 14px rgba(0,0,0,.12);'
            '" />'
            "</a>"
        ),
        url=image_url,
        width=resolved_width,
        height=resolved_height,
        object_fit=object_fit,
        border_radius=resolved_radius,
        background=background,
    )


def unique_copy_key(
    *,
    model,
    source_key: str,
    maximum_length: int = 100,
) -> str:
    """
    Build a unique key for duplicated Admin records.
    """

    normalized_source = (
        str(source_key or "item")
        .strip()
        .lower()
    )

    base_suffix = "-copy"

    base = normalized_source[
        : maximum_length - len(base_suffix)
    ]

    candidate = f"{base}{base_suffix}"
    counter = 2

    while model.objects.filter(
        key=candidate,
    ).exists():
        suffix = f"-copy-{counter}"

        candidate = (
            normalized_source[
                : maximum_length - len(suffix)
            ]
            + suffix
        )

        counter += 1

    return candidate


@transaction.atomic
def reorder_selected_items(
    *,
    queryset,
    start: int = 10,
    step: int = 10,
) -> int:
    """
    Normalize selected sort orders deterministically.
    """

    items = list(
        queryset.order_by(
            "sort_order",
            "id",
        )
    )

    for index, item in enumerate(items):
        item.sort_order = (
            start + index * step
        )

        item.save(
            update_fields=[
                "sort_order",
                "updated_at",
            ]
        )

    return len(items)


def json_pretty_payload(
    value: Any,
) -> str:
    """
    Pretty-print one JSON-compatible value.
    """

    import json

    return json.dumps(
        value,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    )
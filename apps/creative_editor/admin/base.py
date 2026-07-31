# apps/creative_editor/admin/base.py

from __future__ import annotations

from typing import Any

from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString


class CreativeAdminStateActionsMixin:
    """
    Shared activate/deactivate and feature actions.
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
    Render a safe Admin image preview.
    """

    if not image_field:
        return "—"

    try:
        image_url = image_field.url
    except Exception:
        return "Unavailable"

    return format_html(
        (
            '<a href="{0}" target="_blank" rel="noopener">'
            '<img src="{0}" '
            'style="'
            'display:block;'
            'width:{1}px;'
            'height:{2}px;'
            'object-fit:{3};'
            'border-radius:{4}px;'
            'background:{5};'
            'padding:5px;'
            'box-sizing:border-box;'
            'box-shadow:0 4px 14px rgba(0,0,0,.12);'
            '" />'
            "</a>"
        ),
        image_url,
        width,
        height,
        object_fit,
        border_radius,
        background,
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
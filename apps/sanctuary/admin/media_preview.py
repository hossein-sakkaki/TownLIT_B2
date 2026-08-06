# apps/sanctuary/admin/media_preview.py

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import quote

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
)
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.cache import never_cache

from apps.asset_delivery.services.field_aliases import (
    resolve_field_alias,
)
from apps.asset_delivery.services.playback_resolver import (
    resolve_fallback_filefield_key,
)
from apps.asset_delivery.services.signers.cloudfront_signer import (
    build_signed_url,
)
from apps.asset_delivery.services.target_resolver import (
    get_target_by_content_type,
)


logger = logging.getLogger(__name__)


ADMIN_MEDIA_SIGNED_URL_TTL_SECONDS = 120


@dataclass(frozen=True)
class SanctuaryAdminMediaAsset:
    """
    One media asset that may be inspected by a Sanctuary admin.
    """

    field_name: str
    label: str
    kind: str
    inline_preview: bool = False


# Explicit whitelist.
#
# Never accept arbitrary model fields from an admin URL. Only the
# configured fields below can be resolved and signed.
SANCTUARY_ADMIN_MEDIA_FIELDS: dict[
    str,
    tuple[SanctuaryAdminMediaAsset, ...],
] = {
    "accounts.customuser": (
        SanctuaryAdminMediaAsset(
            field_name="image_name",
            label="Profile image",
            kind="image",
            inline_preview=True,
        ),
    ),
    "conversation.dialogue": (
        SanctuaryAdminMediaAsset(
            field_name="group_image",
            label="Group image",
            kind="image",
            inline_preview=True,
        ),
    ),
    "posts.moment": (
        SanctuaryAdminMediaAsset(
            field_name="cover_image",
            label="Moment cover",
            kind="image",
            inline_preview=True,
        ),
        SanctuaryAdminMediaAsset(
            field_name="thumbnail",
            label="Moment thumbnail",
            kind="thumbnail",
            inline_preview=True,
        ),
        SanctuaryAdminMediaAsset(
            field_name="image",
            label="Moment image",
            kind="image",
            inline_preview=True,
        ),
        SanctuaryAdminMediaAsset(
            field_name="video",
            label="Moment video",
            kind="video",
        ),
        SanctuaryAdminMediaAsset(
            field_name="audio",
            label="Moment audio",
            kind="audio",
        ),
    ),
    "posts.prayer": (
        SanctuaryAdminMediaAsset(
            field_name="thumbnail",
            label="Prayer thumbnail",
            kind="thumbnail",
            inline_preview=True,
        ),
        SanctuaryAdminMediaAsset(
            field_name="image",
            label="Prayer image",
            kind="image",
            inline_preview=True,
        ),
        SanctuaryAdminMediaAsset(
            field_name="video",
            label="Prayer video",
            kind="video",
        ),
        SanctuaryAdminMediaAsset(
            field_name="audio",
            label="Prayer audio",
            kind="audio",
        ),
    ),
    "posts.testimony": (
        SanctuaryAdminMediaAsset(
            field_name="thumbnail",
            label="Testimony thumbnail",
            kind="thumbnail",
            inline_preview=True,
        ),
        SanctuaryAdminMediaAsset(
            field_name="artwork",
            label="Audio artwork",
            kind="image",
            inline_preview=True,
        ),
        SanctuaryAdminMediaAsset(
            field_name="image",
            label="Testimony image",
            kind="image",
            inline_preview=True,
        ),
        SanctuaryAdminMediaAsset(
            field_name="video",
            label="Testimony video",
            kind="video",
        ),
        SanctuaryAdminMediaAsset(
            field_name="audio",
            label="Testimony audio",
            kind="audio",
        ),
        SanctuaryAdminMediaAsset(
            field_name="file",
            label="Testimony file",
            kind="file",
        ),
    ),
    "posts.journeyentry": (
        SanctuaryAdminMediaAsset(
            field_name="thumbnail",
            label="Journey thumbnail",
            kind="thumbnail",
            inline_preview=True,
        ),
        SanctuaryAdminMediaAsset(
            field_name="rendered_image",
            label="Journey image",
            kind="image",
            inline_preview=True,
        ),
    ),
}


def _model_key(obj: Any) -> str:
    return (
        f"{obj._meta.app_label}."
        f"{obj._meta.model_name}"
    ).lower()


def _clean_storage_key(value: Any) -> str | None:
    key = str(value or "").strip().lstrip("/")

    if not key:
        return None

    # Storage keys must be relative paths. Reject obvious unsafe
    # traversal or URL-shaped values before signing.
    if ".." in key.split("/"):
        return None

    if "://" in key:
        return None

    return key


def _cdn_base_url() -> str:
    """
    Resolve TownLIT's canonical private asset CDN base URL.

    The authoritative TownLIT setting is:
    ASSET_CDN_BASE_URL=https://cdn.example.com
    """

    direct_candidates = (
        getattr(
            settings,
            "ASSET_CDN_BASE_URL",
            "",
        ),
        # Backward-compatible aliases.
        getattr(
            settings,
            "ASSET_DELIVERY_CDN_BASE_URL",
            "",
        ),
        getattr(
            settings,
            "CLOUDFRONT_BASE_URL",
            "",
        ),
        getattr(
            settings,
            "CDN_BASE_URL",
            "",
        ),
    )

    for raw_value in direct_candidates:
        value = str(
            raw_value or ""
        ).strip()

        if not value:
            continue

        if not value.startswith(
            (
                "http://",
                "https://",
            )
        ):
            value = f"https://{value}"

        return value.rstrip("/")

    domain_candidates = (
        getattr(
            settings,
            "CLOUDFRONT_DOMAIN",
            "",
        ),
        getattr(
            settings,
            "AWS_CLOUDFRONT_DOMAIN",
            "",
        ),
    )

    for raw_domain in domain_candidates:
        domain = str(
            raw_domain or ""
        ).strip()

        if not domain:
            continue

        if domain.startswith(
            (
                "http://",
                "https://",
            )
        ):
            return domain.rstrip("/")

        return (
            f"https://"
            f"{domain.rstrip('/')}"
        )

    raise RuntimeError(
        "ASSET_CDN_BASE_URL is empty. Configure the "
        "CloudFront/CDN base URL, for example: "
        "ASSET_CDN_BASE_URL=https://cdn.townlit.com"
    )

def _resource_url_from_key(
    storage_key: str,
) -> str:
    """
    Build a CloudFront resource URL without exposing S3.

    Slashes remain path separators while unsafe path characters
    are percent-encoded.
    """

    cleaned_key = _clean_storage_key(
        storage_key
    )

    if not cleaned_key:
        raise Http404(
            "The selected media asset is unavailable."
        )

    encoded_path = quote(
        cleaned_key,
        safe="/-_.~",
    )

    return (
        f"{_cdn_base_url()}/"
        f"{encoded_path}"
    )


def _resolve_real_field_name(
    *,
    obj: Any,
    public_field_name: str,
) -> str:
    return resolve_field_alias(
        app_label=obj._meta.app_label,
        model=obj._meta.model_name,
        field_name=public_field_name,
    )


def _resolve_asset_key(
    *,
    obj: Any,
    field_name: str,
) -> str | None:
    """
    Use TownLIT's canonical fallback playback resolver.

    This supports:
    - FileField/ImageField
    - Moment cover_image
    - Moment image_items:<id>
    - Moment image_items:<index>
    """

    resolved_field_name = (
        _resolve_real_field_name(
            obj=obj,
            public_field_name=field_name,
        )
    )

    key = resolve_fallback_filefield_key(
        target_obj=obj,
        field_name=resolved_field_name,
    )

    return _clean_storage_key(
        key
    )


def _normalized_moment_items(
    obj: Any,
) -> list[dict]:
    if _model_key(obj) != "posts.moment":
        return []

    try:
        if hasattr(
            obj,
            "normalized_image_items",
        ):
            items = obj.normalized_image_items()
        else:
            items = getattr(
                obj,
                "image_items",
                None,
            )

        if not isinstance(
            items,
            list,
        ):
            return []

        return [
            item
            for item in items
            if (
                isinstance(item, dict)
                and item.get("key")
            )
        ]
    except Exception:
        logger.exception(
            "Could not resolve Moment image items",
            extra={
                "target_id": getattr(
                    obj,
                    "pk",
                    None,
                ),
            },
        )

        return []


def _moment_dynamic_assets(
    obj: Any,
) -> tuple[
    SanctuaryAdminMediaAsset,
    ...,
]:
    assets: list[
        SanctuaryAdminMediaAsset
    ] = []

    items = sorted(
        _normalized_moment_items(obj),
        key=lambda item: int(
            item.get("order", 0) or 0
        ),
    )

    for index, item in enumerate(items):
        selector = str(
            item.get("id")
            or index
        ).strip()

        if not selector:
            selector = str(index)

        assets.append(
            SanctuaryAdminMediaAsset(
                field_name=(
                    f"image_items:{selector}"
                ),
                label=(
                    f"Moment image {index + 1}"
                ),
                kind="image",
                inline_preview=True,
            )
        )

    return tuple(assets)


def _configured_assets_for(
    obj: Any,
) -> tuple[
    SanctuaryAdminMediaAsset,
    ...,
]:
    configured = (
        SANCTUARY_ADMIN_MEDIA_FIELDS.get(
            _model_key(obj),
            (),
        )
    )

    if _model_key(obj) == "posts.moment":
        return (
            configured
            + _moment_dynamic_assets(obj)
        )

    return configured


def available_admin_media_assets(
    obj: Any,
) -> tuple[
    SanctuaryAdminMediaAsset,
    ...,
]:
    """
    Return only configured assets that currently resolve to a key.
    """

    if obj is None:
        return ()

    available: list[
        SanctuaryAdminMediaAsset
    ] = []

    seen_fields: set[str] = set()

    for asset in _configured_assets_for(
        obj
    ):
        if asset.field_name in seen_fields:
            continue

        key = _resolve_asset_key(
            obj=obj,
            field_name=asset.field_name,
        )

        if not key:
            continue

        seen_fields.add(
            asset.field_name
        )

        available.append(
            asset
        )

    return tuple(available)


def _get_target(
    *,
    content_type_id: int,
    object_id: int,
):
    try:
        return get_target_by_content_type(
            content_type_id=content_type_id,
            object_id=object_id,
        )
    except ContentType.DoesNotExist as exc:
        raise Http404(
            "The requested target type does not exist."
        ) from exc
    except (
        ValueError,
        TypeError,
    ) as exc:
        raise Http404(
            "The requested target is invalid."
        ) from exc
    except Exception as exc:
        # Includes target model DoesNotExist without coupling this
        # module to each possible target model.
        raise Http404(
            "The requested target could not be found."
        ) from exc


def _assert_admin_permission(
    *,
    request: HttpRequest,
    obj: Any,
) -> None:
    user = request.user

    if not getattr(
        user,
        "is_authenticated",
        False,
    ):
        raise PermissionDenied

    if not getattr(
        user,
        "is_active",
        False,
    ):
        raise PermissionDenied

    if not getattr(
        user,
        "is_staff",
        False,
    ):
        raise PermissionDenied

    if getattr(
        user,
        "is_superuser",
        False,
    ):
        return

    sanctuary_permissions = (
        "sanctuary.view_sanctuaryrequest",
        "sanctuary.change_sanctuaryrequest",
    )

    target_permission = (
        f"{obj._meta.app_label}."
        f"view_{obj._meta.model_name}"
    )

    if any(
        user.has_perm(permission)
        for permission in sanctuary_permissions
    ):
        return

    if user.has_perm(
        target_permission
    ):
        return

    raise PermissionDenied(
        "You do not have permission to review "
        "this Sanctuary media."
    )


def _assert_allowed_asset(
    *,
    obj: Any,
    field_name: str,
) -> SanctuaryAdminMediaAsset:
    allowed = {
        asset.field_name: asset
        for asset in available_admin_media_assets(
            obj
        )
    }

    asset = allowed.get(
        field_name
    )

    if asset is None:
        raise Http404(
            "This media asset is not available "
            "for Sanctuary review."
        )

    return asset


def build_admin_signed_media_url(
    *,
    obj: Any,
    field_name: str,
    expires_in: int = (
        ADMIN_MEDIA_SIGNED_URL_TTL_SECONDS
    ),
) -> str:
    """
    Resolve an asset key and sign its CloudFront URL.

    No raw S3 URL is generated or returned.
    """

    asset_key = _resolve_asset_key(
        obj=obj,
        field_name=field_name,
    )

    if not asset_key:
        raise Http404(
            "The selected media asset is unavailable."
        )

    resource_url = _resource_url_from_key(
        asset_key
    )

    signed = build_signed_url(
        resource_url=resource_url,
        expires_in=expires_in,
    )

    return signed.url


def admin_media_preview_url(
    *,
    obj: Any,
    field_name: str,
) -> str:
    content_type = (
        ContentType.objects
        .get_for_model(
            obj,
            for_concrete_model=False,
        )
    )

    return reverse(
        "admin:sanctuary_media_preview",
        kwargs={
            "content_type_id": (
                content_type.pk
            ),
            "object_id": obj.pk,
            "field_name": field_name,
        },
    )


@never_cache
@staff_member_required
def sanctuary_admin_media_preview_view(
    request: HttpRequest,
    content_type_id: int,
    object_id: int,
    field_name: str,
) -> HttpResponse:
    obj = _get_target(
        content_type_id=content_type_id,
        object_id=object_id,
    )

    asset = _assert_allowed_asset(
        obj=obj,
        field_name=field_name,
    )

    _assert_admin_permission(
        request=request,
        obj=obj,
    )

    signed_url = (
        build_admin_signed_media_url(
            obj=obj,
            field_name=field_name,
            expires_in=(
                ADMIN_MEDIA_SIGNED_URL_TTL_SECONDS
            ),
        )
    )

    logger.info(
        "[SanctuaryAdmin] private media preview granted",
        extra={
            "admin_user_id": (
                request.user.pk
            ),
            "target_model": (
                obj._meta.label_lower
            ),
            "target_object_id": obj.pk,
            "field_name": field_name,
            "media_kind": asset.kind,
            "expires_in": (
                ADMIN_MEDIA_SIGNED_URL_TTL_SECONDS
            ),
        },
    )

    response = HttpResponseRedirect(
        signed_url
    )

    response["Cache-Control"] = (
        "private, no-store, no-cache, "
        "must-revalidate, max-age=0"
    )
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    response["Referrer-Policy"] = (
        "same-origin"
    )

    return response


def sanctuary_admin_media_urls():
    return [
        path(
            (
                "sanctuary/media-preview/"
                "<int:content_type_id>/"
                "<int:object_id>/"
                "<path:field_name>/"
            ),
            admin.site.admin_view(
                sanctuary_admin_media_preview_view
            ),
            name="sanctuary_media_preview",
        ),
    ]


def _render_media_action_link(
    *,
    obj: Any,
    asset: SanctuaryAdminMediaAsset,
):
    url = admin_media_preview_url(
        obj=obj,
        field_name=asset.field_name,
    )

    if asset.kind == "video":
        icon = "▶"
    elif asset.kind == "audio":
        icon = "🔊"
    elif asset.kind == "file":
        icon = "📄"
    else:
        icon = "🖼"

    return format_html(
        (
            '<a href="{}" '
            'target="_blank" '
            'rel="noopener noreferrer" '
            'style="'
            "display:inline-block;"
            "margin:3px 8px 3px 0;"
            "padding:6px 10px;"
            "border:1px solid #c9ccd1;"
            "border-radius:6px;"
            "background:#fff;"
            "text-decoration:none;"
            '">'
            "{} {}"
            "</a>"
        ),
        url,
        icon,
        asset.label,
    )


def _first_inline_asset(
    assets: Iterable[
        SanctuaryAdminMediaAsset
    ],
) -> SanctuaryAdminMediaAsset | None:
    for asset in assets:
        if asset.inline_preview:
            return asset

    return None


def sanctuary_admin_media_panel(
    obj: Any,
):
    """
    Render one inline image preview plus links for all assets.

    Video and audio assets are opened in a separate browser tab.
    """

    assets = (
        available_admin_media_assets(
            obj
        )
    )

    if not assets:
        return format_html(
            '<span style="color:#667085;">'
            "No reviewable private media found."
            "</span>"
        )

    action_links = [
        _render_media_action_link(
            obj=obj,
            asset=asset,
        )
        for asset in assets
    ]

    links_html = format_html(
        "".join(
            "{}"
            for _ in action_links
        ),
        *action_links,
    )

    inline_asset = (
        _first_inline_asset(
            assets
        )
    )

    if inline_asset is None:
        return links_html

    preview_url = admin_media_preview_url(
        obj=obj,
        field_name=(
            inline_asset.field_name
        ),
    )

    return format_html(
        (
            '<div style="margin:0 0 12px 0;">'
            '<a href="{0}" '
            'target="_blank" '
            'rel="noopener noreferrer">'
            '<img '
            'src="{0}" '
            'alt="{1}" '
            'loading="lazy" '
            'style="'
            "display:block;"
            "max-width:520px;"
            "max-height:420px;"
            "width:auto;"
            "height:auto;"
            "object-fit:contain;"
            "border-radius:10px;"
            "border:1px solid #d0d5dd;"
            "background:#f8fafc;"
            "padding:4px;"
            '">'
            "</a>"
            '<div style="'
            "margin-top:5px;"
            "color:#667085;"
            "font-size:12px;"
            '">'
            "{1} · signed preview expires shortly"
            "</div>"
            "</div>"
            "<div>{2}</div>"
        ),
        preview_url,
        inline_asset.label,
        links_html,
    )
# apps/core/streams/organization.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

"""An Organization source for the universal /streams/ API, not a second feed."""

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

from apps.organization_content.models import OrganizationUpdate
from apps.organization_content.services.access import can_view_organization_content
from apps.organization_media.serializers import OrganizationMediaAssetSerializer
from apps.organizations.serializers.organization import _organization_file_url

PAGE_SIZE = 7


def _visible(update, viewer):
    return (can_view_organization_content(organization=update.organization, viewer=viewer)
            and update.is_publicly_available)


def _stream_item(update, request, content_type_id):
    assets = [usage.asset for usage in update.media_items.all()]
    rendered = OrganizationMediaAssetSerializer(assets, many=True, context={"request": request}).data
    first = rendered[0] if rendered else None
    kind = (first or {}).get("kind", "written")
    if kind not in {"image", "video"}:
        kind = "written"
    org = update.organization
    preview = {
        "type": kind,
        "thumbnail_url": (first or {}).get("thumbnail_url"),
        "image_url": (first or {}).get("file_url") if kind == "image" else None,
        "poster_url": (first or {}).get("thumbnail_url"),
        "has_video": kind == "video",
        "aspect_ratio": (first or {}).get("aspect_ratio"),
        "duration_ms": (first or {}).get("duration_ms"),
        "preview_video": ({"video_url": first.get("file_url")} if kind == "video" else None),
        "image_items": [
            {"id": str(asset["id"]), "order": index, "image_url": asset.get("file_url"),
             "field_name": "file", "aspect_ratio": asset.get("aspect_ratio")}
            for index, asset in enumerate(rendered) if asset.get("kind") == "image"
        ],
    }
    org_identity = {
        "id": org.pk,
        "public_id": str(org.public_id),
        "slug": org.slug,
        "name": org.name,
        "logo_url": _organization_file_url(org.logo, request=request),
        "thumbnail_url": _organization_file_url(org.thumbnail, request=request),
        "brand_color": getattr(org, "brand_color", None),
    }
    return {
        "kind": "organization_update", "id": update.pk,
        "published_at": update.published_at,
        "owner_user_id": None, "owner_username": None,
        "in_stillness": False, "has_boundary": False,
        "has_boundary_between": False, "direct_interaction_available": True,
        "payload": {
            "id": update.pk, "caption": update.caption, "published_at": update.published_at,
            "preview": preview, "image": (first or {}).get("file_url") if kind == "image" else None,
            "video": (first or {}).get("file_url") if kind == "video" else None,
            "thumbnail": (first or {}).get("thumbnail_url"),
            "organization": org_identity,
            "media_asset_id": (first or {}).get("id"),
            "comment_target": {"content_type_id": content_type_id, "object_id": update.pk},
            "reaction_target": {"content_type_id": content_type_id, "object_id": update.pk},
            "comments_count": update.comments_count if hasattr(update, "comments_count") else 0,
            "reactions_count": update.reactions_count if hasattr(update, "reactions_count") else 0,
            "direct_interaction_available": True,
        },
    }


def organization_stream_page(*, request, context):
    # Scope and kind are validated by StreamViewSet before this call.
    base = (OrganizationUpdate.objects.select_related("organization")
            .prefetch_related("media_items__asset")
            .filter(status=OrganizationUpdate.Status.PUBLISHED,
                    caption_safety_verified=True,
                    published_at__lte=timezone.now(),
                    organization__status="active",
                    organization__visibility__in=["public", "unlisted"]))
    seed = get_object_or_404(base, pk=context.seed_id)
    if not _visible(seed, request.user):
        raise NotFound("Organization content is unavailable.")

    # A stream opened on one card continues through older posts of the same Organization.
    entries = base.filter(organization_id=seed.organization_id)
    if context.cursor:
        cursor = context.cursor
        entries = entries.filter(Q(published_at__lt=cursor.published_at)
                                 | Q(published_at=cursor.published_at, pk__lt=cursor.object_id))
    else:
        entries = entries.filter(Q(published_at__lt=seed.published_at)
                                 | Q(published_at=seed.published_at, pk__lt=seed.pk))

    candidates = entries.order_by("-published_at", "-pk")[:PAGE_SIZE * 6]
    visible = [item for item in candidates if _visible(item, request.user)]
    capacity = PAGE_SIZE - (0 if context.cursor else 1)
    items = ([] if context.cursor else [seed]) + visible[:capacity]
    has_more = len(visible) > capacity
    tail = items[-1] if items else None
    next_cursor = (f"{tail.published_at.isoformat()}|{tail.pk}" if has_more and tail else None)
    content_type_id = ContentType.objects.get_for_model(OrganizationUpdate).pk
    return Response({
        "next": next_cursor,
        "results": [_stream_item(item, request, content_type_id) for item in items],
        "kind": "organization_update", "subtype": None,
        "scope": "organization", "mode": context.mode,
        "extension": 0, "can_continue": has_more,
        "limit_reached": False,
        "policy": {"scope": "organization", "is_limited": False, "batch_size": PAGE_SIZE, "batch_count": 0},
        "composition": {"modules": []},
    })

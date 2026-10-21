# apps/core/square/projections/organization_update.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

"""Square preview for organization-owned updates; no separate media pipeline."""

from .base import SquareProjection
from .registry import register_projection
from .media import cdn_url, media_asset, media_dimensions, variants_payload


@register_projection("organization_update")
class OrganizationUpdateSquareProjection(SquareProjection):
    def get_owner_payload(self):
        # Content belongs to the organization, never the operator.
        return {"owner_user_id": None, "owner_username": None}

    def get_peace_payload(self):
        return {"in_stillness": False, "has_boundary": False,
                "has_boundary_between": False, "direct_interaction_available": True}

    def get_preview(self):
        update = self.obj
        # Final Safety / Sanctuary gate cannot be replaced by SQL alone.
        if not update.is_publicly_available:
            return None

        usages = list(update.media_items.all())
        if not usages:
            return None
        assets = [usage.asset for usage in usages]
        primary = assets[0]
        video = primary.kind == "video"
        field = "thumbnail" if video else "file"
        media = media_asset(primary, field)
        dimensions = media_dimensions(media_asset(primary, "file"))
        image_url = cdn_url(getattr(primary, field, None))
        fallback_thumb = cdn_url(primary.thumbnail) if primary.thumbnail else None
        if video and not image_url:
            image_url = fallback_thumb

        images = []
        for index, asset in enumerate(assets):
            if asset.kind != "image":
                continue
            key = str(asset.file.name or "").lstrip("/")
            url = cdn_url(key)
            images.append({
                "id": str(asset.pk), "key": key, "order": index,
                "field_name": "file", "is_cover": asset.pk == primary.pk,
                "image_url": url, "cdn_url": url, "url": url,
                "variants": variants_payload(media_asset(asset, "file").get("variants")),
            })

        # Preview URLs are a fallback; iOS resolves media through the shared
        # authenticated MediaRepository with the actual OrganizationMediaAsset id.
        return {
            "type": "video" if video else "image", "has_video": video,
            "image_url": None if video else image_url,
            "thumbnail_url": image_url if video else None,
            "poster_url": image_url,
            "width": dimensions.get("width"),
            "height": dimensions.get("height"),
            "aspect_ratio": dimensions.get("aspect_ratio"),
            "duration_ms": media_asset(primary, "file").get("duration_ms"),
            "variants": variants_payload(media.get("variants")),
            "image_items": images,
            "cover_image_id": str(primary.pk),
            "cover_image": {
                "id": str(primary.pk), "field_name": field,
                "source": "organization_media", "image_url": image_url,
                "variants": variants_payload(media.get("variants")),
            },
        }

    def get_meta(self):
        organization = self.obj.organization
        logo = organization.logo
        return {
            "title": organization.name,
            "excerpt": (self.obj.caption or "")[:160],
            "organization_name": organization.name,
            "organization_slug": organization.slug,
            "organization_public_id": str(organization.public_id),
            "organization_logo_url": cdn_url(logo),
        }

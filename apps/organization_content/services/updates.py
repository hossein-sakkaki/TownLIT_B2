# apps/organization_content/services/updates.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-28.
# Last Update by Hossein Sakkaki on 2026-09-28.

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organization_content.feature_flags import (
    ensure_organization_content_writes_enabled,
)
from apps.organization_content.models import (
    OrganizationUpdate,
    OrganizationUpdateMedia,
)
from apps.organization_content.services.feed import set_home_visibility
from apps.organization_media.models import OrganizationMediaAsset
from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationPermissionKey,
)
from apps.organizations.models import OrganizationAuditLog
from apps.organizations.services.access import user_has_organization_permission


def _ensure_manager(*, actor, organization):
    if not user_has_organization_permission(
        user=actor,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_ANNOUNCEMENTS,
    ):
        raise PermissionDenied(
            "You do not have permission to manage Organization updates."
        )


def _normalize_caption(value):
    value = str(value or "").strip()

    if not value:
        raise ValidationError({
            "caption": "Caption is required.",
        })

    return value


def _resolve_assets(*, organization, public_ids):
    public_ids = list(dict.fromkeys(public_ids or []))

    if not public_ids:
        return []

    assets = list(
        OrganizationMediaAsset.objects.filter(
            organization=organization,
            public_id__in=public_ids,
            status=OrganizationMediaAsset.Status.READY,
        )
    )

    by_id = {
        str(asset.public_id): asset
        for asset in assets
    }

    ordered = []

    for public_id in public_ids:
        asset = by_id.get(str(public_id))

        if not asset:
            raise ValidationError({
                "media_public_ids": (
                    f"Ready Organization media asset "
                    f"{public_id} was not found."
                )
            })

        ordered.append(asset)

    return ordered


def _replace_media(*, update, assets):
    update.media_items.all().delete()

    for index, asset in enumerate(assets):
        usage = OrganizationUpdateMedia(
            update=update,
            asset=asset,
            sort_order=index,
        )
        usage.full_clean()
        usage.save()


def _audit(*, update, actor, event):
    OrganizationAuditLog.objects.create(
        organization=update.organization,
        action=OrganizationAuditAction.ORGANIZATION_UPDATED,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        metadata={
            "section": "organization_content",
            "event": event,
            "update_public_id": str(update.public_id),
        },
    )


@transaction.atomic
def create_update(*, organization, actor, caption, media_public_ids=None):
    ensure_organization_content_writes_enabled()
    _ensure_manager(actor=actor, organization=organization)

    update = OrganizationUpdate(
        organization=organization,
        caption=_normalize_caption(caption),
        created_by=actor,
    )
    update.full_clean()
    update.save()

    assets = _resolve_assets(
        organization=organization,
        public_ids=media_public_ids,
    )
    _replace_media(update=update, assets=assets)

    _audit(
        update=update,
        actor=actor,
        event="update_created",
    )

    return update


@transaction.atomic
def update_update(*, update, actor, validated_data):
    ensure_organization_content_writes_enabled()

    update = OrganizationUpdate.objects.select_for_update().select_related(
        "organization"
    ).get(pk=update.pk)

    _ensure_manager(
        actor=actor,
        organization=update.organization,
    )

    if update.status == OrganizationUpdate.Status.ARCHIVED:
        raise ValidationError(
            "Archived Organization updates cannot be edited."
        )

    if "caption" in validated_data:
        update.caption = _normalize_caption(
            validated_data["caption"]
        )

    update.full_clean()
    update.save()

    if "media_public_ids" in validated_data:
        assets = _resolve_assets(
            organization=update.organization,
            public_ids=validated_data["media_public_ids"],
        )
        _replace_media(
            update=update,
            assets=assets,
        )

    _audit(
        update=update,
        actor=actor,
        event="update_updated",
    )

    return update


@transaction.atomic
def publish_update(
    *,
    update,
    actor,
    publish_at=None,
    show_on_home=True,
    starts_at=None,
    expires_at=None,
    is_pinned=False,
):
    ensure_organization_content_writes_enabled()

    update = OrganizationUpdate.objects.select_for_update().select_related(
        "organization"
    ).get(pk=update.pk)

    _ensure_manager(
        actor=actor,
        organization=update.organization,
    )

    if update.status != OrganizationUpdate.Status.DRAFT:
        raise ValidationError(
            "Only draft Organization updates can be published."
        )

    if update.media_items.exclude(
        asset__status=OrganizationMediaAsset.Status.READY
    ).exists():
        raise ValidationError(
            "All attached media assets must be ready before publishing."
        )

    publish_at = publish_at or timezone.now()
    feed_starts_at = starts_at or publish_at

    if feed_starts_at < publish_at:
        raise ValidationError({
            "starts_at": (
                "Home visibility cannot begin before publication."
            )
        })

    if expires_at and expires_at <= feed_starts_at:
        raise ValidationError({
            "expires_at": (
                "Expiration must be after the display start time."
            )
        })

    update.status = OrganizationUpdate.Status.PUBLISHED
    update.published_by = actor
    update.published_at = publish_at
    update.archived_at = None

    update.full_clean()
    update.save()

    if show_on_home:
        set_home_visibility(
            organization=update.organization,
            target=update,
            show=True,
            starts_at=feed_starts_at,
            expires_at=expires_at,
            is_pinned=is_pinned,
        )

    _audit(
        update=update,
        actor=actor,
        event="update_published",
    )

    return update


@transaction.atomic
def archive_update(*, update, actor):
    ensure_organization_content_writes_enabled()

    update = OrganizationUpdate.objects.select_for_update().select_related(
        "organization"
    ).get(pk=update.pk)

    _ensure_manager(
        actor=actor,
        organization=update.organization,
    )

    if update.status == OrganizationUpdate.Status.ARCHIVED:
        return update

    update.status = OrganizationUpdate.Status.ARCHIVED
    update.archived_at = timezone.now()

    update.full_clean()
    update.save()

    set_home_visibility(
        organization=update.organization,
        target=update,
        show=False,
    )

    _audit(
        update=update,
        actor=actor,
        event="update_archived",
    )

    return update


@transaction.atomic
def set_update_home_visibility(
    *,
    update,
    actor,
    show,
    starts_at=None,
    expires_at=None,
    is_pinned=False,
):
    ensure_organization_content_writes_enabled()

    update = OrganizationUpdate.objects.select_for_update().select_related(
        "organization"
    ).get(pk=update.pk)

    _ensure_manager(
        actor=actor,
        organization=update.organization,
    )

    if update.status != OrganizationUpdate.Status.PUBLISHED:
        raise ValidationError(
            "Only published Organization updates can appear on the home feed."
        )

    display_start = starts_at or update.published_at or timezone.now()

    if update.published_at and display_start < update.published_at:
        raise ValidationError({
            "starts_at": (
                "Home visibility cannot begin before publication."
            )
        })

    if expires_at and expires_at <= display_start:
        raise ValidationError({
            "expires_at": (
                "Expiration must be after the display start time."
            )
        })

    entry = set_home_visibility(
        organization=update.organization,
        target=update,
        show=show,
        starts_at=display_start,
        expires_at=expires_at,
        is_pinned=is_pinned,
    )

    _audit(
        update=update,
        actor=actor,
        event=(
            "home_visibility_enabled"
            if show
            else "home_visibility_disabled"
        ),
    )

    return entry
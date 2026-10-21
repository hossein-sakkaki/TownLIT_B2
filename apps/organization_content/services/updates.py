# apps/organization_content/services/updates.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-28.
# Last Update by Hossein Sakkaki on 2026-10-20.

import uuid

from django.core.exceptions import ValidationError
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
from apps.organization_content.services.access import (
    ensure_content_manager, ensure_update_editable, ensure_update_revision,
)
from apps.organization_content.services.content_safety import enforce_update_caption_safety
from apps.organization_content.publishing_policy import MAX_CAPTION_WORDS, validate_media_selection


def _ensure_manager(*, actor, organization):
    ensure_content_manager(actor=actor, organization=organization)


def _normalize_caption(value):
    value = str(value or "").strip()

    if not value:
        raise ValidationError({
            "caption": "Caption is required.",
        })

    if len(value.split()) > MAX_CAPTION_WORDS:
        raise ValidationError({"caption": f"Use no more than {MAX_CAPTION_WORDS} words."})
    return value


def _resolve_assets(*, organization, public_ids, allow_pending=False):
    public_ids = list(dict.fromkeys(public_ids or []))

    if not public_ids:
        return []

    assets = list(
        OrganizationMediaAsset.objects.filter(
            organization=organization,
            public_id__in=public_ids,
        )
    )

    by_id = {
        str(asset.public_id): asset
        for asset in assets
    }

    ordered = []

    for public_id in public_ids:
        asset = by_id.get(str(public_id))

        if not asset or asset.status == OrganizationMediaAsset.Status.ARCHIVED:
            raise ValidationError({
                "media_public_ids": (
                    f"Ready Organization media asset "
                    f"{public_id} was not found."
                )
            })

        if not allow_pending and not asset.is_ready_for_publication():
            raise ValidationError({"media_public_ids": "All media must pass safety checks and finish processing."})
        ordered.append(asset)

    validate_media_selection(ordered)
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
def create_update(*, organization, actor, caption, media_public_ids=None, public_id=None):
    ensure_organization_content_writes_enabled()
    _ensure_manager(actor=actor, organization=organization)

    caption = _normalize_caption(caption)
    organization = organization.__class__.objects.select_for_update().get(pk=organization.pk)
    _ensure_manager(actor=actor, organization=organization)
    if public_id:
        existing = OrganizationUpdate.objects.filter(public_id=public_id).first()
        if existing is not None:
            if (existing.organization_id != organization.pk
                    or existing.created_by_id != actor.pk):
                raise ValidationError({"public_id": "This submission identifier is already in use."})
            return existing
    enforce_update_caption_safety(caption=caption, actor=actor)
    update = OrganizationUpdate(
        public_id=public_id or uuid.uuid4(), organization=organization,
        caption=caption, created_by=actor, caption_safety_verified=True,
    )
    update.full_clean()
    update.save()

    assets = _resolve_assets(
        organization=organization,
        public_ids=media_public_ids, allow_pending=True,
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

    ensure_update_editable(update)
    if update.publish_requested_at and update.status == OrganizationUpdate.Status.DRAFT:
        raise ValidationError("A submitted post cannot be modified while publishing is pending.")
    ensure_update_revision(update=update, expected_updated_at=validated_data.get("expected_updated_at"))

    if "caption" in validated_data:
        caption = _normalize_caption(validated_data["caption"])
        enforce_update_caption_safety(
            caption=caption, actor=actor,
            instance=update if update.caption_safety_verified else None,
        )
        update.caption = caption
        update.caption_safety_verified = True

    update.full_clean()
    update.save()

    if "media_public_ids" in validated_data:
        assets = _resolve_assets(
            organization=update.organization,
            public_ids=validated_data["media_public_ids"],
            allow_pending=update.status == OrganizationUpdate.Status.DRAFT,
        )
        validate_media_selection(
            assets, require_media=update.status == OrganizationUpdate.Status.PUBLISHED,
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
    expected_updated_at=None,
):
    ensure_organization_content_writes_enabled()

    update = OrganizationUpdate.objects.select_for_update().select_related(
        "organization"
    ).get(pk=update.pk)

    _ensure_manager(
        actor=actor,
        organization=update.organization,
    )

    if update.status == OrganizationUpdate.Status.PUBLISHED:
        return update
    ensure_update_editable(update)
    ensure_update_revision(update=update, expected_updated_at=expected_updated_at)
    if update.status != OrganizationUpdate.Status.DRAFT:
        raise ValidationError("Only draft Organization updates can be published.")
    if not update.is_active or update.is_suspended:
        raise ValidationError("This Organization content cannot be published.")
    from apps.sanctuary.services.held_content_access import is_under_active_safety_hold
    if is_under_active_safety_hold(update):
        raise ValidationError("This Organization content is under review.")
    enforce_update_caption_safety(caption=update.caption, actor=actor)
    update.caption_safety_verified = True
    assets = [usage.asset for usage in update.media_items.select_related("asset")]
    validate_media_selection(assets, require_media=True)
    if any(not asset.is_ready_for_publication() for asset in assets):
        raise ValidationError("All attached media must pass safety checks and finish processing before publishing.")

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


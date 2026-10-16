# apps/organization_content/services/feed.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-28.

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.organization_content.models import (
    OrganizationFeedEntry,
    OrganizationUpdate,
)


def _target_organization_id(target):
    if isinstance(target, OrganizationUpdate):
        return target.organization_id

    from apps.organization_media.models import ChurchTeachingContent

    if isinstance(target, ChurchTeachingContent):
        return target.workspace.activation.organization_id

    return None


def _target_is_public(target):
    if isinstance(target, OrganizationUpdate):
        return target.is_publicly_available

    from apps.organization_media.models import ChurchTeachingContent

    if isinstance(target, ChurchTeachingContent):
        return (
            target.status == "published"
            and target.audience == "public"
            and target.workspace.activation.status == "enabled"
            and target.workspace.activation.visibility == "public"
            and target.workspace.activation.organization.status == "active"
            and target.workspace.activation.organization.visibility == "public"
            and target.is_available()
        )

    return False


def feed_entry_for_target(*, organization, target):
    content_type = ContentType.objects.get_for_model(
        target,
        for_concrete_model=False,
    )

    return OrganizationFeedEntry.objects.filter(
        organization=organization,
        content_type=content_type,
        object_id=str(target.pk),
    ).first()


@transaction.atomic
def set_home_visibility(
    *,
    organization,
    target,
    show,
    expires_at=None,
    starts_at=None,
    is_pinned=False,
):
    if _target_organization_id(target) != organization.pk:
        raise ValidationError(
            "Target is unsupported or belongs to a different Organization."
        )

    content_type = ContentType.objects.get_for_model(
        target,
        for_concrete_model=False,
    )

    if not show:
        entry = OrganizationFeedEntry.objects.select_for_update().filter(
            organization=organization,
            content_type=content_type,
            object_id=str(target.pk),
        ).first()

        if entry:
            entry.is_active = False
            entry.is_pinned = False
            entry.save(
                update_fields=[
                    "is_active",
                    "is_pinned",
                    "updated_at",
                ]
            )

        return entry

    entry, _ = OrganizationFeedEntry.objects.select_for_update().get_or_create(
        organization=organization,
        content_type=content_type,
        object_id=str(target.pk),
        defaults={
            "source": (
                OrganizationFeedEntry.Source.UPDATE
                if isinstance(target, OrganizationUpdate)
                else OrganizationFeedEntry.Source.MODULE
            ),
        },
    )

    entry.source = (
        OrganizationFeedEntry.Source.UPDATE
        if isinstance(target, OrganizationUpdate)
        else OrganizationFeedEntry.Source.MODULE
    )
    entry.is_active = True
    entry.is_pinned = bool(is_pinned)
    entry.starts_at = starts_at or timezone.now()
    entry.expires_at = expires_at

    entry.full_clean()
    entry.save()

    return entry


def visible_feed(organization, *, now=None):
    now = now or timezone.now()

    if organization.status != "active" or organization.visibility != "public":
        return []

    entries = (
        OrganizationFeedEntry.objects
        .filter(
            organization=organization,
            is_active=True,
            starts_at__lte=now,
        )
        .filter(
            Q(expires_at__isnull=True)
            | Q(expires_at__gt=now)
        )
        .select_related("content_type")
        .order_by(
            "-is_pinned",
            "-starts_at",
            "-pk",
        )
    )

    return [
        entry
        for entry in entries
        if entry.content_object
        and _target_organization_id(entry.content_object) == organization.pk
        and _target_is_public(entry.content_object)
    ]
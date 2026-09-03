# apps/organizations/modules/church/services/campuses.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchCampusStatus,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.models import ChurchCampus
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit
from apps.organizations.modules.church.services.slugs import unique_workspace_slug


@transaction.atomic
def create_church_campus(
    *,
    workspace,
    actor,
    name,
    description=None,
    address=None,
    public_email=None,
    public_phone=None,
    website_url=None,
    timezone_override=None,
    is_primary=False,
    sort_order=100,
):
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_CAMPUSES,
    )

    has_active_campus = ChurchCampus.objects.filter(
        workspace=workspace,
        status=ChurchCampusStatus.ACTIVE,
    ).exists()

    campus = ChurchCampus(
        workspace=workspace,
        name=name,
        slug=unique_workspace_slug(
            model=ChurchCampus,
            workspace=workspace,
            name=name,
        ),
        description=description,
        address=address,
        public_email=public_email,
        public_phone=public_phone,
        website_url=website_url,
        timezone_override=timezone_override,
        is_primary=(is_primary or not has_active_campus),
        sort_order=sort_order,
    )

    if campus.is_primary:
        ChurchCampus.objects.select_for_update().filter(
            workspace=workspace,
            is_primary=True,
        ).update(
            is_primary=False,
            primary_slot=None,
        )

    campus.full_clean()
    campus.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.CAMPUS_CREATED,
        actor=actor,
        entity=campus,
        metadata={
            "name": campus.name,
            "is_primary": campus.is_primary,
        },
    )

    return campus


@transaction.atomic
def set_primary_church_campus(*, campus, actor):
    campus = (
        ChurchCampus.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=campus.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=campus.workspace,
        permission_key=ChurchPermissionKey.MANAGE_CAMPUSES,
    )

    if campus.status != ChurchCampusStatus.ACTIVE:
        raise ValidationError(
            "Only active church campuses can become primary."
        )

    ChurchCampus.objects.select_for_update().filter(
        workspace=campus.workspace,
        is_primary=True,
    ).exclude(pk=campus.pk).update(
        is_primary=False,
        primary_slot=None,
    )

    campus.is_primary = True
    campus.full_clean()
    campus.save(update_fields=["is_primary", "updated_at"])

    record_church_audit(
        workspace=campus.workspace,
        event=ChurchAuditEvent.CAMPUS_PRIMARY_CHANGED,
        actor=actor,
        entity=campus,
    )

    return campus


@transaction.atomic
def update_church_campus(
    *,
    campus,
    actor,
    name=None,
    description=None,
    address=None,
    public_email=None,
    public_phone=None,
    website_url=None,
    timezone_override=None,
    sort_order=None,
):
    campus = (
        ChurchCampus.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=campus.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=campus.workspace,
        permission_key=ChurchPermissionKey.MANAGE_CAMPUSES,
    )

    if name is not None:
        campus.name = name
        campus.slug = unique_workspace_slug(
            model=ChurchCampus,
            workspace=campus.workspace,
            name=name,
            exclude_pk=campus.pk,
        )
    if description is not None:
        campus.description = description
    if address is not None:
        campus.address = address
    if public_email is not None:
        campus.public_email = public_email or None
    if public_phone is not None:
        campus.public_phone = public_phone or None
    if website_url is not None:
        campus.website_url = website_url or None
    if timezone_override is not None:
        campus.timezone_override = timezone_override or None
    if sort_order is not None:
        campus.sort_order = sort_order

    campus.full_clean()
    campus.save()

    record_church_audit(
        workspace=campus.workspace,
        event=ChurchAuditEvent.CAMPUS_UPDATED,
        actor=actor,
        entity=campus,
    )

    return campus


@transaction.atomic
def archive_church_campus(*, campus, actor):
    campus = (
        ChurchCampus.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=campus.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=campus.workspace,
        permission_key=ChurchPermissionKey.MANAGE_CAMPUSES,
    )

    if campus.is_primary:
        raise ValidationError(
            "Transfer the primary campus designation before archiving this campus."
        )

    campus.status = ChurchCampusStatus.ARCHIVED
    campus.is_primary = False
    campus.full_clean()
    campus.save(
        update_fields=[
            "status",
            "is_primary",
            "updated_at",
        ]
    )

    record_church_audit(
        workspace=campus.workspace,
        event=ChurchAuditEvent.CAMPUS_ARCHIVED,
        actor=actor,
        entity=campus,
    )

    return campus

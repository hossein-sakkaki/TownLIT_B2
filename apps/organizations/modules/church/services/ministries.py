 # apps/organizations/modules/church/services/ministries.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchMinistryMembershipStatus,
    ChurchMinistryParticipationRole,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.models import (
    ChurchMinistry,
    ChurchMinistryMembership,
)
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit
from apps.organizations.modules.church.services.slugs import unique_workspace_slug


@transaction.atomic
def create_church_ministry(
    *,
    workspace,
    actor,
    name,
    campus=None,
    description=None,
    visibility="public",
    is_accepting_participants=True,
    sort_order=100,
):
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_MINISTRIES,
    )

    ministry = ChurchMinistry(
        workspace=workspace,
        campus=campus,
        name=name,
        slug=unique_workspace_slug(
            model=ChurchMinistry,
            workspace=workspace,
            name=name,
        ),
        description=description,
        visibility=visibility,
        is_accepting_participants=is_accepting_participants,
        sort_order=sort_order,
    )
    ministry.full_clean()
    ministry.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.MINISTRY_CREATED,
        actor=actor,
        entity=ministry,
        metadata={"name": ministry.name},
    )

    return ministry


@transaction.atomic
def update_church_ministry(
    *,
    ministry,
    actor,
    name=None,
    campus=None,
    description=None,
    visibility=None,
    status=None,
    is_accepting_participants=None,
    sort_order=None,
):
    ministry = (
        ChurchMinistry.objects
        .select_for_update()
        .select_related("workspace__activation__organization", "campus")
        .get(pk=ministry.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=ministry.workspace,
        permission_key=ChurchPermissionKey.MANAGE_MINISTRIES,
    )

    if name is not None:
        ministry.name = name
        ministry.slug = unique_workspace_slug(
            model=ChurchMinistry,
            workspace=ministry.workspace,
            name=name,
            exclude_pk=ministry.pk,
        )
    if campus is not None:
        ministry.campus = campus
    if description is not None:
        ministry.description = description
    if visibility is not None:
        ministry.visibility = visibility
    if status is not None:
        ministry.status = status
    if is_accepting_participants is not None:
        ministry.is_accepting_participants = is_accepting_participants
    if sort_order is not None:
        ministry.sort_order = sort_order

    ministry.full_clean()
    ministry.save()

    record_church_audit(
        workspace=ministry.workspace,
        event=ChurchAuditEvent.MINISTRY_UPDATED,
        actor=actor,
        entity=ministry,
    )

    return ministry


@transaction.atomic
def add_church_ministry_participant(
    *,
    ministry,
    membership,
    actor,
    participation_role=ChurchMinistryParticipationRole.PARTICIPANT,
    publicly_listed=False,
):
    ministry = (
        ChurchMinistry.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=ministry.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=ministry.workspace,
        permission_key=ChurchPermissionKey.MANAGE_MINISTRIES,
    )

    if membership.status != OrganizationMembershipStatus.ACTIVE:
        raise ValidationError(
            "Only active organization members can join church ministries."
        )

    existing = ChurchMinistryMembership.objects.filter(
        ministry=ministry,
        membership=membership,
        status=ChurchMinistryMembershipStatus.ACTIVE,
    ).first()

    if existing:
        return existing

    participant = ChurchMinistryMembership(
        ministry=ministry,
        membership=membership,
        participation_role=participation_role,
        is_publicly_listed=publicly_listed,
    )
    participant.full_clean()
    participant.save()

    record_church_audit(
        workspace=ministry.workspace,
        event=ChurchAuditEvent.MINISTRY_PARTICIPANT_ADDED,
        actor=actor,
        membership=membership,
        entity=participant,
        metadata={
            "ministry_public_id": str(ministry.public_id),
            "participation_role": participant.participation_role,
        },
    )

    return participant


@transaction.atomic
def remove_church_ministry_participant(*, participant, actor, now=None):
    now = now or timezone.now()
    participant = (
        ChurchMinistryMembership.objects
        .select_for_update()
        .select_related(
            "ministry__workspace__activation__organization",
            "membership__member__user",
        )
        .get(pk=participant.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=participant.ministry.workspace,
        permission_key=ChurchPermissionKey.MANAGE_MINISTRIES,
    )

    if participant.status == ChurchMinistryMembershipStatus.ENDED:
        return participant

    participant.status = ChurchMinistryMembershipStatus.ENDED
    participant.ended_at = now
    participant.full_clean()
    participant.save(
        update_fields=[
            "status",
            "ended_at",
            "updated_at",
        ]
    )

    record_church_audit(
        workspace=participant.ministry.workspace,
        event=ChurchAuditEvent.MINISTRY_PARTICIPANT_REMOVED,
        actor=actor,
        membership=participant.membership,
        entity=participant,
        metadata={
            "ministry_public_id": str(participant.ministry.public_id),
        },
    )

    return participant

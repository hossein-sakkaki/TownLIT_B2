# apps/organizations/modules/church/services/serving_teams.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchPermissionKey,
    ChurchServingAssignmentStatus,
    ChurchServingTeamMembershipStatus,
)
from apps.organizations.modules.church.models import (
    ChurchServingAssignment,
    ChurchServingTeam,
    ChurchServingTeamMembership,
)
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit
from apps.organizations.modules.church.services.slugs import unique_workspace_slug


@transaction.atomic
def create_church_serving_team(
    *,
    workspace,
    actor,
    name,
    campus=None,
    ministry=None,
    description=None,
    sort_order=100,
):
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVING_TEAMS,
    )

    team = ChurchServingTeam(
        workspace=workspace,
        campus=campus,
        ministry=ministry,
        name=name,
        slug=unique_workspace_slug(
            model=ChurchServingTeam,
            workspace=workspace,
            name=name,
        ),
        description=description,
        sort_order=sort_order,
    )
    team.full_clean()
    team.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.SERVING_TEAM_CREATED,
        actor=actor,
        entity=team,
        metadata={"name": team.name},
    )

    return team


@transaction.atomic
def update_church_serving_team(
    *,
    team,
    actor,
    name=None,
    campus=None,
    ministry=None,
    description=None,
    status=None,
    sort_order=None,
):
    team = (
        ChurchServingTeam.objects
        .select_for_update()
        .select_related("workspace__activation__organization", "campus", "ministry")
        .get(pk=team.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=team.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVING_TEAMS,
    )

    if name is not None:
        team.name = name
        team.slug = unique_workspace_slug(
            model=ChurchServingTeam,
            workspace=team.workspace,
            name=name,
            exclude_pk=team.pk,
        )
    if campus is not None:
        team.campus = campus
    if ministry is not None:
        team.ministry = ministry
    if description is not None:
        team.description = description
    if status is not None:
        team.status = status
    if sort_order is not None:
        team.sort_order = sort_order

    team.full_clean()
    team.save()

    record_church_audit(
        workspace=team.workspace,
        event=ChurchAuditEvent.SERVING_TEAM_UPDATED,
        actor=actor,
        entity=team,
    )

    return team


@transaction.atomic
def add_church_serving_team_member(
    *,
    team,
    membership,
    actor,
    role_title=None,
    is_team_lead=False,
    publicly_listed=False,
):
    team = (
        ChurchServingTeam.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=team.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=team.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVING_TEAMS,
    )

    if membership.status != OrganizationMembershipStatus.ACTIVE:
        raise ValidationError(
            "Only active organization members can join Church serving teams."
        )

    existing = ChurchServingTeamMembership.objects.filter(
        team=team,
        membership=membership,
        status=ChurchServingTeamMembershipStatus.ACTIVE,
    ).first()

    if existing:
        return existing

    team_membership = ChurchServingTeamMembership(
        team=team,
        membership=membership,
        role_title=role_title,
        is_team_lead=is_team_lead,
        is_publicly_listed=publicly_listed,
    )
    team_membership.full_clean()
    team_membership.save()

    record_church_audit(
        workspace=team.workspace,
        event=ChurchAuditEvent.SERVING_TEAM_MEMBER_ADDED,
        actor=actor,
        membership=membership,
        entity=team_membership,
        metadata={
            "team_public_id": str(team.public_id),
            "role_title": team_membership.role_title,
            "is_team_lead": team_membership.is_team_lead,
        },
    )

    return team_membership


@transaction.atomic
def remove_church_serving_team_member(*, team_membership, actor, now=None):
    now = now or timezone.now()
    team_membership = (
        ChurchServingTeamMembership.objects
        .select_for_update()
        .select_related("team__workspace__activation__organization", "membership")
        .get(pk=team_membership.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=team_membership.team.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVING_TEAMS,
    )

    if team_membership.status == ChurchServingTeamMembershipStatus.ENDED:
        return team_membership

    if ChurchServingAssignment.objects.filter(
        team=team_membership.team,
        membership=team_membership.membership,
        status__in={
            ChurchServingAssignmentStatus.INVITED,
            ChurchServingAssignmentStatus.CONFIRMED,
        },
    ).exists():
        raise ValidationError(
            "Active serving assignments must be resolved before ending team membership."
        )

    team_membership.status = ChurchServingTeamMembershipStatus.ENDED
    team_membership.ended_at = now
    team_membership.full_clean()
    team_membership.save(
        update_fields=["status", "ended_at", "updated_at"]
    )

    record_church_audit(
        workspace=team_membership.team.workspace,
        event=ChurchAuditEvent.SERVING_TEAM_MEMBER_REMOVED,
        actor=actor,
        membership=team_membership.membership,
        entity=team_membership,
        metadata={
            "team_public_id": str(team_membership.team.public_id),
        },
    )

    return team_membership

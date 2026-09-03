# apps/organizations/modules/church/services/households.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchHouseholdMembershipStatus,
    ChurchHouseholdRelationship,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.models import ChurchHousehold, ChurchHouseholdMembership
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit


@transaction.atomic
def create_church_household(*, workspace, actor, name, campus=None):
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_HOUSEHOLDS,
    )

    household = ChurchHousehold(
        workspace=workspace,
        name=(name or "").strip(),
        campus=campus,
        created_by=actor,
    )
    household.full_clean()
    household.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.HOUSEHOLD_CREATED,
        actor=actor,
        entity=household,
    )
    return household


@transaction.atomic
def update_church_household(*, household, actor, name=None, campus=None):
    household = ChurchHousehold.objects.select_for_update().select_related("workspace").get(pk=household.pk)
    ensure_church_permission(
        actor=actor,
        workspace=household.workspace,
        permission_key=ChurchPermissionKey.MANAGE_HOUSEHOLDS,
    )

    if name is not None:
        household.name = (name or "").strip()
    if campus is not None:
        household.campus = campus
    household.full_clean()
    household.save()

    record_church_audit(
        workspace=household.workspace,
        event=ChurchAuditEvent.HOUSEHOLD_UPDATED,
        actor=actor,
        entity=household,
    )
    return household


@transaction.atomic
def add_church_household_member(
    *,
    household,
    congregant,
    actor,
    relationship_type=ChurchHouseholdRelationship.OTHER,
    is_primary=False,
):
    household = ChurchHousehold.objects.select_for_update().select_related("workspace").get(pk=household.pk)
    ensure_church_permission(
        actor=actor,
        workspace=household.workspace,
        permission_key=ChurchPermissionKey.MANAGE_HOUSEHOLDS,
    )

    if congregant.workspace_id != household.workspace_id:
        raise ValidationError({"congregant": "Household member must belong to the same Church workspace."})
    if not congregant.is_active:
        raise ValidationError({"congregant": "Inactive congregation records cannot join an active household."})

    existing = (
        ChurchHouseholdMembership.objects
        .select_for_update()
        .filter(
            household=household,
            congregant=congregant,
            status=ChurchHouseholdMembershipStatus.ACTIVE,
        )
        .first()
    )
    if existing:
        return existing

    if ChurchHouseholdMembership.objects.filter(
        congregant=congregant,
        status=ChurchHouseholdMembershipStatus.ACTIVE,
    ).exists():
        raise ValidationError({"congregant": "Congregant already belongs to an active Church household."})

    if is_primary:
        ChurchHouseholdMembership.objects.filter(
            household=household,
            status=ChurchHouseholdMembershipStatus.ACTIVE,
            is_primary=True,
        ).update(is_primary=False, primary_slot=None)

    membership = ChurchHouseholdMembership(
        household=household,
        congregant=congregant,
        relationship_type=relationship_type,
        is_primary=is_primary,
    )
    membership.full_clean()
    membership.save()

    record_church_audit(
        workspace=household.workspace,
        event=ChurchAuditEvent.HOUSEHOLD_MEMBER_ADDED,
        actor=actor,
        entity=membership,
        metadata={"relationship_type": relationship_type, "is_primary": is_primary},
    )
    return membership


@transaction.atomic
def remove_church_household_member(*, household_membership, actor):
    household_membership = (
        ChurchHouseholdMembership.objects
        .select_for_update()
        .select_related("household__workspace")
        .get(pk=household_membership.pk)
    )
    ensure_church_permission(
        actor=actor,
        workspace=household_membership.household.workspace,
        permission_key=ChurchPermissionKey.MANAGE_HOUSEHOLDS,
    )

    if household_membership.status == ChurchHouseholdMembershipStatus.ENDED:
        return household_membership

    household_membership.status = ChurchHouseholdMembershipStatus.ENDED
    household_membership.is_primary = False
    household_membership.ended_at = timezone.now()
    household_membership.full_clean()
    household_membership.save()

    record_church_audit(
        workspace=household_membership.household.workspace,
        event=ChurchAuditEvent.HOUSEHOLD_MEMBER_REMOVED,
        actor=actor,
        entity=household_membership,
    )
    return household_membership

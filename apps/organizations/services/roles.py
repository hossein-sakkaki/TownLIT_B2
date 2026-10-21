# apps/organizations/services/roles.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-10-20.
#

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    DEFAULT_PERMISSION_DEFINITIONS,
    DEFAULT_ROLE_DEFINITIONS,
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationPermissionKey,
    OrganizationRoleKey,
    OrganizationRoleScope,
)
from apps.organizations.models import (
    OrganizationAuditLog,
    OrganizationMembership,
    OrganizationPermission,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRolePermission,
)
from apps.organizations.services.access import (
    user_has_organization_permission_strict,
)
from apps.organizations.services.lifecycle_policy import (
    require_operational_organization,
)


@transaction.atomic
def bootstrap_organization_access(organization):
    permissions = {}

    for key, name, category in DEFAULT_PERMISSION_DEFINITIONS:
        permission, _ = OrganizationPermission.objects.get_or_create(
            key=key,
            defaults={
                "name": name,
                "category": category,
                "is_active": True,
            },
        )

        update_fields = []

        if permission.name != name:
            permission.name = name
            update_fields.append("name")

        if permission.category != category:
            permission.category = category
            update_fields.append("category")

        if not permission.is_active:
            permission.is_active = True
            update_fields.append("is_active")

        if update_fields:
            update_fields.append("updated_at")
            permission.save(update_fields=update_fields)

        permissions[key] = permission

    roles = {}

    for definition in DEFAULT_ROLE_DEFINITIONS:
        role, _ = OrganizationRole.objects.get_or_create(
            organization=organization,
            key=definition["key"],
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "priority": definition["priority"],
                "is_system": True,
                "is_protected": definition["is_protected"],
                "is_active": True,
            },
        )

        role.name = definition["name"]
        role.description = definition["description"]
        role.priority = definition["priority"]
        role.is_system = True
        role.is_protected = definition["is_protected"]
        role.is_active = True
        role.save(
            update_fields=[
                "name",
                "description",
                "priority",
                "is_system",
                "is_protected",
                "is_active",
                "updated_at",
            ]
        )

        expected_permission_ids = {
            permissions[key].id
            for key in definition["permissions"]
        }

        OrganizationRolePermission.objects.filter(
            role=role,
        ).exclude(
            permission_id__in=expected_permission_ids,
        ).delete()

        for permission_id in expected_permission_ids:
            OrganizationRolePermission.objects.get_or_create(
                role=role,
                permission_id=permission_id,
            )

        roles[role.key] = role

    return roles


# Protected domains require an Owner (or explicit platform staff authority)
# even when the actor holds another management permission.
_OWNER_DELEGATED_ONLY_PERMISSIONS = frozenset({
    OrganizationPermissionKey.MANAGE_BILLING,
    OrganizationPermissionKey.MANAGE_VERIFICATION,
    OrganizationPermissionKey.MANAGE_GOVERNANCE,
})


def _active_organization_assignments(*, organization, user, now):
    return OrganizationRoleAssignment.objects.filter(
        membership__organization=organization,
        membership__member__user=user,
        membership__status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
        is_active=True,
        revoked_at__isnull=True,
        starts_at__lte=now,
        role__is_active=True,
        scope_type=OrganizationRoleScope.ORGANIZATION,
        scope_key="",
    ).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gt=now)
    )


def _require_role_delegation(*, actor, organization, role):
    if not actor or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("An authenticated actor is required to manage roles.")

    # Platform staff retains its existing administrative bypass. Every action
    # is still recorded in OrganizationAuditLog with the real actor.
    if getattr(actor, "is_staff", False):
        return

    if not user_has_organization_permission_strict(
        user=actor,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_ROLES,
    ):
        raise PermissionDenied(
            "You do not have permission to manage organization roles."
        )

    now = timezone.now()
    assignments = _active_organization_assignments(
        organization=organization,
        user=actor,
        now=now,
    )

    if assignments.filter(
        role__key=OrganizationRoleKey.OWNER,
        role__is_protected=True,
    ).exists():
        return

    target_permissions = set(
        role.role_permissions.values_list("permission__key", flat=True)
    )
    if target_permissions & _OWNER_DELEGATED_ONLY_PERMISSIONS:
        raise PermissionDenied(
            "Only an Organization Owner can delegate billing, "
            "verification, or governance authority."
        )

    actor_permissions = set(
        assignments.values_list(
            "role__role_permissions__permission__key", flat=True
        )
    )
    actor_permissions.discard(None)
    if not target_permissions.issubset(actor_permissions):
        raise PermissionDenied(
            "You cannot assign or revoke a role with permissions "
            "outside your own Organization authority."
        )

    highest_priority = (
        assignments.order_by("-role__priority")
        .values_list("role__priority", flat=True)
        .first()
    )
    if highest_priority is None or role.priority > highest_priority:
        raise PermissionDenied(
            "You cannot manage a role with higher priority than your own."
        )


@transaction.atomic
def assign_organization_role(
    *,
    membership,
    role,
    actor=None,
    scope_type=OrganizationRoleScope.ORGANIZATION,
    scope_key="",
    bypass_protection=False,
):
    # Lock the Organization first, then membership/role rows.
    # This matches governance lifecycle transitions and reduces deadlock risk.
    if not bypass_protection:
        require_operational_organization(organization=membership.organization)

    membership = (
        OrganizationMembership.objects
        .select_for_update()
        .select_related(
            "organization",
            "member__user",
        )
        .get(pk=membership.pk)
    )
    role = OrganizationRole.objects.select_for_update().get(
        pk=role.pk
    )

    if not role.is_active:
        raise ValidationError("Inactive roles cannot be assigned.")

    if membership.status not in ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES:
        raise ValidationError(
            "Roles can only be assigned to current organization members."
        )

    if role.organization_id != membership.organization_id:
        raise ValidationError(
            "Role and membership belong to different organizations."
        )

    if scope_type == OrganizationRoleScope.MODULE:
        from apps.organizations.models import OrganizationModuleActivation

        normalized_scope_key = str(scope_key or "").strip().lower()

        if not normalized_scope_key:
            raise ValidationError(
                "Module-scoped roles require a module scope key."
            )

        if not OrganizationModuleActivation.objects.filter(
            organization=membership.organization,
            module__key=normalized_scope_key,
        ).exists():
            raise ValidationError(
                "Module-scoped roles require an existing module activation."
            )

        scope_key = normalized_scope_key

    if role.is_protected and not bypass_protection:
        raise ValidationError(
            "Protected roles can only be changed through a protected workflow."
        )

    if not bypass_protection:
        _require_role_delegation(
            actor=actor,
            organization=membership.organization,
            role=role,
        )

    existing = OrganizationRoleAssignment.objects.filter(
        membership=membership,
        role=role,
        scope_type=scope_type,
        scope_key=scope_key,
        is_active=True,
    ).first()

    if existing:
        return existing

    assignment = OrganizationRoleAssignment(
        membership=membership,
        role=role,
        scope_type=scope_type,
        scope_key=scope_key,
        assigned_by=actor,
    )
    assignment.full_clean()
    assignment.save()

    OrganizationAuditLog.objects.create(
        organization=membership.organization,
        action=OrganizationAuditAction.ROLE_ASSIGNED,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        target_user=membership.member.user,
        membership=membership,
        role_assignment=assignment,
        metadata={
            "role_key": role.key,
            "scope_type": scope_type,
            "scope_key": scope_key,
        },
    )

    return assignment


@transaction.atomic
def revoke_organization_role(
    *,
    assignment,
    actor=None,
    bypass_protection=False,
    now=None,
):
    now = now or timezone.now()

    if not bypass_protection:
        require_operational_organization(
            organization=assignment.membership.organization
        )

    assignment = (
        OrganizationRoleAssignment.objects
        .select_for_update()
        .select_related(
            "role",
            "membership__organization",
            "membership__member__user",
        )
        .get(pk=assignment.pk)
    )

    organization = assignment.membership.organization

    if not assignment.is_active:
        return assignment

    if assignment.role.is_protected and not bypass_protection:
        raise ValidationError(
            "Protected roles can only be changed through a protected workflow."
        )

    if not bypass_protection:
        _require_role_delegation(
            actor=actor,
            organization=organization,
            role=assignment.role,
        )

    assignment.is_active = False
    assignment.revoked_at = now
    assignment.save(
        update_fields=[
            "is_active",
            "revoked_at",
            "updated_at",
        ]
    )

    OrganizationAuditLog.objects.create(
        organization=organization,
        action=OrganizationAuditAction.ROLE_REVOKED,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        target_user=assignment.membership.member.user,
        membership=assignment.membership,
        role_assignment=assignment,
        metadata={
            "role_key": assignment.role.key,
            "scope_type": assignment.scope_type,
            "scope_key": assignment.scope_key,
        },
    )

    return assignment


def get_owner_role(organization):
    return OrganizationRole.objects.get(
        organization=organization,
        key=OrganizationRoleKey.OWNER,
        is_active=True,
    )


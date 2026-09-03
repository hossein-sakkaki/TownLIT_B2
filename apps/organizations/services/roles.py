# apps/organizations/services/roles.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
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
    user_has_organization_permission,
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

    if actor and not bypass_protection:
        if not user_has_organization_permission(
            user=actor,
            organization=membership.organization,
            permission_key=OrganizationPermissionKey.MANAGE_ROLES,
        ):
            raise PermissionDenied(
                "You do not have permission to manage organization roles."
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

    if not assignment.is_active:
        return assignment

    if assignment.role.is_protected and not bypass_protection:
        raise ValidationError(
            "Protected roles can only be changed through a protected workflow."
        )

    organization = assignment.membership.organization

    if actor and not bypass_protection:
        if not user_has_organization_permission(
            user=actor,
            organization=organization,
            permission_key=OrganizationPermissionKey.MANAGE_ROLES,
        ):
            raise PermissionDenied(
                "You do not have permission to manage organization roles."
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

# apps/organizations/modules/church/services/bootstrap.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.organizations.constants import OrganizationModuleKey
from apps.organizations.models import (
    OrganizationPermission,
    OrganizationRole,
    OrganizationRolePermission,
)
from apps.organizations.modules.church.constants import (
    CHURCH_PERMISSION_DEFINITIONS,
    CHURCH_ROLE_DEFINITIONS,
    ChurchAuditEvent,
)
from apps.organizations.modules.church.models import ChurchWorkspace
from apps.organizations.modules.church.services.audit import record_church_audit


@transaction.atomic
def bootstrap_church_workspace(*, activation, actor=None):
    activation = (
        activation.__class__.objects
        .select_for_update()
        .select_related("organization", "module")
        .get(pk=activation.pk)
    )

    if activation.module.key != OrganizationModuleKey.CHURCH:
        raise ValidationError(
            "Church workspace bootstrap requires a Church module activation."
        )

    workspace, created = ChurchWorkspace.objects.get_or_create(
        activation=activation,
    )

    permissions = {}

    for key, name, category, description in CHURCH_PERMISSION_DEFINITIONS:
        permission, _ = OrganizationPermission.objects.get_or_create(
            key=key,
            defaults={
                "name": name,
                "category": category,
                "description": description,
                "is_active": True,
            },
        )

        permission.name = name
        permission.category = category
        permission.description = description
        permission.is_active = True
        permission.save(
            update_fields=[
                "name",
                "category",
                "description",
                "is_active",
                "updated_at",
            ]
        )
        permissions[key] = permission

    for definition in CHURCH_ROLE_DEFINITIONS:
        role, _ = OrganizationRole.objects.get_or_create(
            organization=activation.organization,
            key=definition["key"],
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "priority": definition["priority"],
                "is_system": True,
                "is_protected": False,
                "is_active": True,
            },
        )

        role.name = definition["name"]
        role.description = definition["description"]
        role.priority = definition["priority"]
        role.is_system = True
        role.is_protected = False
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

    if created:
        record_church_audit(
            workspace=workspace,
            event=ChurchAuditEvent.WORKSPACE_INITIALIZED,
            actor=actor,
            entity=workspace,
            metadata={
                "module_activation_public_id": str(activation.public_id),
            },
        )

    return workspace

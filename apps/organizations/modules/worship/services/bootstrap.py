# apps/organizations/modules/worship/services/bootstrap.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.organizations.constants import OrganizationModuleKey
from apps.organizations.models import OrganizationPermission, OrganizationRole, OrganizationRolePermission
from apps.organizations.modules.worship.constants import WORSHIP_PERMISSION_DEFINITIONS, WORSHIP_ROLE_DEFINITIONS, WorshipAuditEvent
from apps.organizations.modules.worship.models import WorshipWorkspace
from apps.organizations.modules.worship.services.audit import record_worship_audit


@transaction.atomic
def bootstrap_worship_workspace(*, activation, actor=None):
    activation = activation.__class__.objects.select_for_update().select_related("organization", "module").get(pk=activation.pk)
    if activation.module.key != OrganizationModuleKey.WORSHIP:
        raise ValidationError("Worship workspace bootstrap requires a Worship module activation.")
    workspace, created = WorshipWorkspace.objects.get_or_create(activation=activation)
    permissions = {}
    for key, name, category, description in WORSHIP_PERMISSION_DEFINITIONS:
        permission, _ = OrganizationPermission.objects.get_or_create(key=key, defaults={"name": name, "category": category, "description": description, "is_active": True})
        permission.name, permission.category, permission.description, permission.is_active = name, category, description, True
        permission.save(update_fields=["name", "category", "description", "is_active", "updated_at"])
        permissions[key] = permission
    for definition in WORSHIP_ROLE_DEFINITIONS:
        role, _ = OrganizationRole.objects.get_or_create(organization=activation.organization, key=definition["key"], defaults={"name": definition["name"], "description": definition["description"], "priority": definition["priority"], "is_system": True, "is_protected": False, "is_active": True})
        role.name, role.description, role.priority = definition["name"], definition["description"], definition["priority"]
        role.is_system, role.is_protected, role.is_active = True, False, True
        role.save(update_fields=["name", "description", "priority", "is_system", "is_protected", "is_active", "updated_at"])
        expected = {permissions[key].id for key in definition["permissions"]}
        OrganizationRolePermission.objects.filter(role=role).exclude(permission_id__in=expected).delete()
        for permission_id in expected:
            OrganizationRolePermission.objects.get_or_create(role=role, permission_id=permission_id)
    if created:
        record_worship_audit(workspace=workspace, event=WorshipAuditEvent.WORKSPACE_INITIALIZED, actor=actor, entity=workspace, metadata={"module_activation_public_id": str(activation.public_id)})
    return workspace

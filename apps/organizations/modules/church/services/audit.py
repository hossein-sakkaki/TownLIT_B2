# apps/organizations/modules/church/services/audit.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from apps.organizations.modules.church.models import ChurchAuditLog


def record_church_audit(
    *,
    workspace,
    event,
    actor=None,
    membership=None,
    entity=None,
    entity_type=None,
    entity_public_id=None,
    metadata=None,
):
    resolved_entity_type = entity_type or (
        entity.__class__.__name__ if entity is not None else "church_workspace"
    )
    resolved_entity_public_id = entity_public_id or (
        getattr(entity, "public_id", None)
        if entity is not None
        else workspace.public_id
    )

    return ChurchAuditLog.objects.create(
        workspace=workspace,
        event=event,
        actor=actor,
        membership=membership,
        entity_type=resolved_entity_type,
        entity_public_id=resolved_entity_public_id,
        metadata=metadata or {},
    )

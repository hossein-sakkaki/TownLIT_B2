# apps/organizations/modules/worship/services/audit.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from apps.organizations.modules.worship.models import WorshipAuditLog


def record_worship_audit(*, workspace, event, actor=None, membership=None, entity=None, entity_type=None, metadata=None):
    resolved_type = entity_type or (entity.__class__.__name__ if entity is not None else "worship_workspace")
    public_id = getattr(entity, "public_id", None) if entity is not None else workspace.public_id
    return WorshipAuditLog.objects.create(
        workspace=workspace, event=event, actor=actor, membership=membership,
        entity_type=resolved_type, entity_public_id=public_id, metadata=metadata or {},
    )

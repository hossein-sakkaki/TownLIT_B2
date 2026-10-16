# apps/conversation/services/organization/direct_audit.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from apps.organizations.constants import OrganizationAuditSource
from apps.organizations.models.audit import OrganizationAuditLog


def log_organization_direct_audit(
    *,
    context,
    action,
    actor=None,
    membership=None,
    metadata=None,
    source=OrganizationAuditSource.SERVICE,
):
    payload = {
        "conversation_context_public_id": str(context.public_id),
        "dialogue_id": context.dialogue_id,
        "dialogue_slug": context.dialogue.slug,
        "participant_user_id": context.participant_user_id,
        **(metadata or {}),
    }
    return OrganizationAuditLog.objects.create(
        organization=context.organization,
        action=action,
        source=source,
        actor=actor,
        target_user=context.participant_user,
        membership=membership,
        metadata=payload,
    )


__all__ = [
    "log_organization_direct_audit",
]

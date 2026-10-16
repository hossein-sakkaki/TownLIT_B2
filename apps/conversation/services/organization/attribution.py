# apps/conversation/services/organization/attribution.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from apps.conversation.models import OrganizationMessageAttribution


def actor_display_name_snapshot(user) -> str:
    full_name = " ".join(
        part.strip()
        for part in (
            str(getattr(user, "name", "") or ""),
            str(getattr(user, "family", "") or ""),
        )
        if part.strip()
    )
    return full_name or str(getattr(user, "username", "") or "Organization operator")


def create_organization_message_attribution(
    *,
    message,
    organization,
    actor_membership,
):
    actor = message.sender
    attribution = OrganizationMessageAttribution(
        message=message,
        organization=organization,
        actor_membership=actor_membership,
        actor_display_name_snapshot=actor_display_name_snapshot(actor),
        actor_username_snapshot=str(getattr(actor, "username", "") or ""),
        actor_membership_public_id_snapshot=(
            actor_membership.public_id
            if actor_membership is not None
            else None
        ),
    )
    attribution.full_clean()
    attribution.save()
    return attribution

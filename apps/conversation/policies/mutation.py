# apps/conversation/policies/mutation.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .context import ConversationContextKind, ConversationContextPolicy


class ConversationMutationAction(str, Enum):
    ADD_PARTICIPANT = "add_participant"
    REMOVE_PARTICIPANT = "remove_participant"
    LEAVE_GROUP = "leave_group"
    DELETE_GROUP = "delete_group"
    TRANSFER_FOUNDER = "transfer_founder"
    PROMOTE_TO_ELDER = "promote_to_elder"
    DEMOTE_TO_PARTICIPANT = "demote_to_participant"
    RESIGN_ELDER = "resign_elder"
    UPDATE_GROUP_INFO = "update_group_info"
    UPDATE_GROUP_IMAGE = "update_group_image"


@dataclass(frozen=True)
class ConversationMutationDecision:
    allowed: bool
    code: str = ""
    message: str = ""


class ConversationMutationPolicy:
    """Protect system-managed conversation contexts from group mutations."""

    @classmethod
    def check(
        cls,
        *,
        dialogue,
        action: ConversationMutationAction,
    ) -> ConversationMutationDecision:
        context = ConversationContextPolicy.resolve(dialogue)

        if (
            context.kind
            == ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY
        ):
            return ConversationMutationDecision(
                allowed=False,
                code="organization_community_system_managed",
                message=(
                    "Members Community membership and group structure "
                    "are managed by Organization membership lifecycle."
                ),
            )

        if context.kind != ConversationContextKind.PERSONAL_GROUP:
            return ConversationMutationDecision(
                allowed=False,
                code="group_mutation_not_applicable",
                message="This mutation is only applicable to personal groups.",
            )

        return ConversationMutationDecision(allowed=True)

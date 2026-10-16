# apps/conversation/policies/security.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .context import ConversationContextKind, ConversationContextPolicy


class ConversationSecurityMode(str, Enum):
    END_TO_END_ENCRYPTED = "end_to_end_encrypted"
    BACKEND_MANAGED = "backend_managed"


@dataclass(frozen=True)
class ConversationSecurityDecision:
    mode: ConversationSecurityMode
    backend_readable: bool
    uses_personal_message_encryption: bool
    requires_personal_e2ee_keys: bool
    content_safety_eligible: bool


class ConversationSecurityPolicy:
    """Separate security semantics from Dialogue.is_group topology."""

    @classmethod
    def resolve(cls, dialogue) -> ConversationSecurityDecision:
        context = ConversationContextPolicy.resolve(dialogue)

        if context.kind == ConversationContextKind.PERSONAL_DIRECT:
            return ConversationSecurityDecision(
                mode=ConversationSecurityMode.END_TO_END_ENCRYPTED,
                backend_readable=False,
                uses_personal_message_encryption=True,
                requires_personal_e2ee_keys=True,
                content_safety_eligible=False,
            )

        return ConversationSecurityDecision(
            mode=ConversationSecurityMode.BACKEND_MANAGED,
            backend_readable=True,
            uses_personal_message_encryption=False,
            requires_personal_e2ee_keys=False,
            content_safety_eligible=True,
        )

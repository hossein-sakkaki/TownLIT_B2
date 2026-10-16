# apps/conversation/policies/context.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from apps.conversation.constants import OrganizationConversationContextType


class ConversationContextKind(str, Enum):
    PERSONAL_DIRECT = "personal_direct"
    PERSONAL_GROUP = "personal_group"
    ORGANIZATION_DIRECT = "organization_direct"
    ORGANIZATION_MEMBERS_COMMUNITY = "organization_members_community"


class ConversationContextResolutionError(ValueError):
    """Raised when persisted conversation context is internally inconsistent."""


@dataclass(frozen=True)
class ResolvedConversationContext:
    kind: ConversationContextKind
    dialogue: Any
    organization_context: Any | None = None

    @property
    def is_personal(self) -> bool:
        return self.kind in {
            ConversationContextKind.PERSONAL_DIRECT,
            ConversationContextKind.PERSONAL_GROUP,
        }

    @property
    def is_organization(self) -> bool:
        return not self.is_personal

    @property
    def is_direct(self) -> bool:
        return self.kind in {
            ConversationContextKind.PERSONAL_DIRECT,
            ConversationContextKind.ORGANIZATION_DIRECT,
        }

    @property
    def is_group(self) -> bool:
        return not self.is_direct


class ConversationContextPolicy:
    """Resolve semantic conversation context from one canonical Dialogue."""

    @classmethod
    def resolve(cls, dialogue) -> ResolvedConversationContext:
        if dialogue is None:
            raise ConversationContextResolutionError(
                "Dialogue is required to resolve conversation context."
            )

        organization_context = getattr(
            dialogue,
            "organization_context",
            None,
        )

        if organization_context is None:
            kind = (
                ConversationContextKind.PERSONAL_GROUP
                if bool(getattr(dialogue, "is_group", False))
                else ConversationContextKind.PERSONAL_DIRECT
            )
            return ResolvedConversationContext(
                kind=kind,
                dialogue=dialogue,
            )

        context_type = getattr(
            organization_context,
            "context_type",
            None,
        )

        if context_type == OrganizationConversationContextType.DIRECT:
            if bool(getattr(dialogue, "is_group", False)):
                raise ConversationContextResolutionError(
                    "Organization Direct context cannot use a group Dialogue."
                )
            return ResolvedConversationContext(
                kind=ConversationContextKind.ORGANIZATION_DIRECT,
                dialogue=dialogue,
                organization_context=organization_context,
            )

        if context_type == OrganizationConversationContextType.MEMBERS_COMMUNITY:
            if not bool(getattr(dialogue, "is_group", False)):
                raise ConversationContextResolutionError(
                    "Members Community context requires a group Dialogue."
                )
            return ResolvedConversationContext(
                kind=(
                    ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY
                ),
                dialogue=dialogue,
                organization_context=organization_context,
            )

        raise ConversationContextResolutionError(
            f"Unsupported Organization conversation context: {context_type!r}."
        )

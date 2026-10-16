# apps/conversation/policies/access.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from dataclasses import dataclass

from apps.conversation.constants import OrganizationConversationStatus
from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    OrganizationPermissionKey,
    OrganizationStatus,
)
from apps.organizations.selectors import is_organization_verified
from apps.organizations.services.access import (
    get_current_membership_for_user,
    user_has_organization_permission_strict,
)

from .context import ConversationContextKind, ConversationContextPolicy


@dataclass(frozen=True)
class ConversationAccessDecision:
    allowed: bool
    code: str = ""
    message: str = ""


class ConversationAccessPolicy:
    """Authorize conversation capabilities without relying on topology alone."""

    @staticmethod
    def _allow() -> ConversationAccessDecision:
        return ConversationAccessDecision(allowed=True)

    @staticmethod
    def _deny(code: str, message: str) -> ConversationAccessDecision:
        return ConversationAccessDecision(
            allowed=False,
            code=code,
            message=message,
        )

    @staticmethod
    def _is_authenticated(user) -> bool:
        return bool(
            user
            and getattr(user, "is_authenticated", False)
        )

    @staticmethod
    def _is_dialogue_participant(dialogue, user) -> bool:
        if not user or getattr(user, "id", None) is None:
            return False
        return dialogue.participants.filter(id=user.id).exists()

    @staticmethod
    def _organization_messenger_is_available(
        organization,
        *,
        now=None,
    ) -> bool:
        if not organization:
            return False
        if getattr(organization, "status", None) != OrganizationStatus.ACTIVE:
            return False
        return bool(
            is_organization_verified(
                organization=organization,
                now=now,
            )
        )

    @staticmethod
    def _has_messenger_permission(
        *,
        user,
        organization,
        permission_keys,
        now=None,
    ) -> bool:
        return any(
            user_has_organization_permission_strict(
                user=user,
                organization=organization,
                permission_key=permission_key,
                now=now,
            )
            for permission_key in permission_keys
        )

    @classmethod
    def _community_membership_is_eligible(
        cls,
        *,
        dialogue,
        organization,
        user,
    ) -> bool:
        if not cls._is_dialogue_participant(dialogue, user):
            return False

        membership = get_current_membership_for_user(
            organization=organization,
            user=user,
        )
        return bool(
            membership
            and membership.status in ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES
        )

    @classmethod
    def can_view(
        cls,
        *,
        dialogue,
        user,
        now=None,
    ) -> ConversationAccessDecision:
        if not cls._is_authenticated(user):
            return cls._deny(
                "authentication_required",
                "Authentication is required.",
            )

        context = ConversationContextPolicy.resolve(dialogue)

        if context.kind in {
            ConversationContextKind.PERSONAL_DIRECT,
            ConversationContextKind.PERSONAL_GROUP,
        }:
            if cls._is_dialogue_participant(dialogue, user):
                return cls._allow()
            return cls._deny(
                "not_dialogue_participant",
                "User is not a participant of this conversation.",
            )

        organization_context = context.organization_context
        organization = organization_context.organization

        if context.kind == ConversationContextKind.ORGANIZATION_DIRECT:
            if (
                getattr(user, "id", None)
                == organization_context.participant_user_id
                and cls._is_dialogue_participant(dialogue, user)
            ):
                # Preserve participant-side read-only history if capability
                # later becomes unavailable.
                return cls._allow()

            if not cls._organization_messenger_is_available(
                organization,
                now=now,
            ):
                return cls._deny(
                    "organization_messenger_unavailable",
                    "Organization Messenger is not currently available.",
                )

            if cls._has_messenger_permission(
                user=user,
                organization=organization,
                permission_keys=(
                    OrganizationPermissionKey.VIEW_MESSENGER,
                    OrganizationPermissionKey.MANAGE_MESSENGER,
                ),
                now=now,
            ):
                return cls._allow()

            return cls._deny(
                "organization_messenger_forbidden",
                "Organization Messenger access is not permitted.",
            )

        if not cls._organization_messenger_is_available(
            organization,
            now=now,
        ):
            return cls._deny(
                "organization_messenger_unavailable",
                "Organization Messenger is not currently available.",
            )

        if cls._community_membership_is_eligible(
            dialogue=dialogue,
            organization=organization,
            user=user,
        ):
            return cls._allow()

        return cls._deny(
            "community_membership_required",
            "An active Organization membership is required.",
        )

    @classmethod
    def can_send_as_self(
        cls,
        *,
        dialogue,
        user,
        now=None,
    ) -> ConversationAccessDecision:
        if not cls._is_authenticated(user):
            return cls._deny(
                "authentication_required",
                "Authentication is required.",
            )

        context = ConversationContextPolicy.resolve(dialogue)

        if context.kind in {
            ConversationContextKind.PERSONAL_DIRECT,
            ConversationContextKind.PERSONAL_GROUP,
        }:
            return cls.can_view(
                dialogue=dialogue,
                user=user,
                now=now,
            )

        organization_context = context.organization_context
        organization = organization_context.organization

        if not cls._organization_messenger_is_available(
            organization,
            now=now,
        ):
            return cls._deny(
                "organization_messenger_unavailable",
                "Organization Messenger is not currently available.",
            )

        if context.kind == ConversationContextKind.ORGANIZATION_DIRECT:
            if (
                getattr(user, "id", None)
                != organization_context.participant_user_id
                or not cls._is_dialogue_participant(dialogue, user)
            ):
                return cls._deny(
                    "organization_identity_required",
                    "Organization operators reply as the Organization.",
                )

            if (
                organization_context.status
                == OrganizationConversationStatus.CLOSED
            ):
                return cls._deny(
                    "organization_conversation_closed",
                    "This Organization conversation is closed.",
                )

            return cls._allow()

        if cls._community_membership_is_eligible(
            dialogue=dialogue,
            organization=organization,
            user=user,
        ):
            return cls._allow()

        return cls._deny(
            "community_membership_required",
            "An active Organization membership is required.",
        )

    @classmethod
    def can_send_as_organization(
        cls,
        *,
        dialogue,
        user,
        now=None,
    ) -> ConversationAccessDecision:
        if not cls._is_authenticated(user):
            return cls._deny(
                "authentication_required",
                "Authentication is required.",
            )

        context = ConversationContextPolicy.resolve(dialogue)
        if not context.is_organization:
            return cls._deny(
                "organization_context_required",
                "This conversation is not an Organization context.",
            )

        organization_context = context.organization_context
        organization = organization_context.organization

        if not cls._organization_messenger_is_available(
            organization,
            now=now,
        ):
            return cls._deny(
                "organization_messenger_unavailable",
                "Organization Messenger is not currently available.",
            )

        if (
            context.kind == ConversationContextKind.ORGANIZATION_DIRECT
            and organization_context.status
            == OrganizationConversationStatus.CLOSED
        ):
            return cls._deny(
                "organization_conversation_closed",
                "This Organization conversation is closed.",
            )

        if (
            context.kind
            == ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY
            and not cls._community_membership_is_eligible(
                dialogue=dialogue,
                organization=organization,
                user=user,
            )
        ):
            return cls._deny(
                "community_membership_required",
                "An active Organization membership is required.",
            )

        if cls._has_messenger_permission(
            user=user,
            organization=organization,
            permission_keys=(
                OrganizationPermissionKey.REPLY_MESSENGER,
                OrganizationPermissionKey.MANAGE_MESSENGER,
            ),
            now=now,
        ):
            return cls._allow()

        return cls._deny(
            "organization_reply_forbidden",
            "Reply-as-Organization permission is required.",
        )

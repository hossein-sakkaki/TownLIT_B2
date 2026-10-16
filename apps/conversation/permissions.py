# apps/conversation/permissions.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from rest_framework.permissions import BasePermission

from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationContextKind,
    ConversationContextPolicy,
)
from apps.core.security.access import has_litshield_access


class ConversationAccessPermission(BasePermission):
    message = "PIN access is required to use this feature."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        return has_litshield_access("conversation", request)


class IsDialogueParticipant(BasePermission):
    def has_object_permission(self, request, view, obj):
        dialogue = obj.dialogue
        context = ConversationContextPolicy.resolve(dialogue)

        if (
            context.kind
            != ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY
        ):
            return request.user in dialogue.participants.all()

        access = ConversationAccessPolicy.can_view(
            dialogue=dialogue,
            user=request.user,
        )
        if not access.allowed:
            return False

        return (
            dialogue.visible_messages_for_user(request.user)
            .filter(id=obj.id)
            .exists()
        )

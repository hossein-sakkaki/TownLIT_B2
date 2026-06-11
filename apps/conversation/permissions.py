from rest_framework.permissions import BasePermission

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
        return request.user in obj.dialogue.participants.all()
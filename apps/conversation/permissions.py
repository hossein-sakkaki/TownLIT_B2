from rest_framework.permissions import BasePermission

class ConversationAccessPermission(BasePermission):
    message = 'PIN access is required to use this feature.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "pin_security_enabled", False):
            return request.COOKIES.get("conversation_access") == "granted"
        return True

    

class IsDialogueParticipant(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user in obj.dialogue.participants.all()
# utils/security/security_manager.py

from apps.profiles.models import Member

class SecurityStateManager:
    """
    Handles reversible + irreversible security state transitions.
    Used by both access PIN and delete PIN flows.
    """

    @staticmethod
    def unhide_confidants(user):
        """Restore confidants after Access PIN or disabling PIN security."""
        try:
            member = user.member_profile
            if member.hide_confidants:
                member.hide_confidants = False
                member.save(update_fields=["hide_confidants"])
        except Member.DoesNotExist:
            pass

    @staticmethod
    def hide_confidants(user):
        """Hide confidants during Destructive PIN action."""
        try:
            member = user.member_profile
            if not member.hide_confidants:
                member.hide_confidants = True
                member.save(update_fields=["hide_confidants"])
        except Member.DoesNotExist:
            pass

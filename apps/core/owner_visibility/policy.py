# apps/core/owner_visibility/policy.py

class OwnerVisibilityPolicy:
    """
    Discovery eligibility (Square/Search/Explore).
    NOT for direct object access.
    """

    # ---------------- HARD BLOCK ----------------
    @staticmethod
    def is_owner_globally_blocked(user, member) -> bool:
        if not user:
            return True

        if user.is_deleted:
            return True

        if user.is_suspended:
            return True

        if user.is_account_paused:
            return True

        if member and not member.is_active:
            return True

        if member and member.is_hidden_by_confidants:
            return True

        return False


    # ---------------- PUBLIC SQUARE ----------------
    @staticmethod
    def is_publicly_discoverable(user, member) -> bool:
        if OwnerVisibilityPolicy.is_owner_globally_blocked(user, member):
            return False

        if member and member.is_privacy:
            return False

        return True


    # ---------------- FRIENDS SQUARE ----------------
    @staticmethod
    def is_friends_discoverable(user, member) -> bool:
        if OwnerVisibilityPolicy.is_owner_globally_blocked(user, member):
            return False

        return True
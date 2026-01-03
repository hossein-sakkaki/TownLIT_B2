# apps/core/visibility/policy.py

from .constants import (
    VISIBILITY_DEFAULT,
    VISIBILITY_GLOBAL,
    VISIBILITY_FRIENDS,
    VISIBILITY_COVENANT,
    VISIBILITY_PRIVATE,
)
from .utils import is_owner
from .selectors import (
    is_profile_private,
    are_friends,
    is_in_covenant,
)


class VisibilityPolicy:
    """
    Central visibility decision engine.
    Single source of truth for ALL post-like content.
    """

    @staticmethod
    def can_view(*, viewer, obj) -> bool:
        # -------------------------------------------------
        # 1️⃣ Moderation gates
        # -------------------------------------------------
        if not obj.is_active or obj.is_hidden:
            return False

        # -------------------------------------------------
        # 2️⃣ Owner always can view
        # -------------------------------------------------
        if viewer and is_owner(viewer, obj):
            return True

        # -------------------------------------------------
        # 3️⃣ Explicit visibility override
        # -------------------------------------------------
        if obj.visibility == VISIBILITY_PRIVATE:
            return False

        if obj.visibility == VISIBILITY_GLOBAL:
            return True

        owner = obj.content_object

        if obj.visibility == VISIBILITY_FRIENDS:
            return viewer is not None and are_friends(viewer, owner)

        if obj.visibility == VISIBILITY_COVENANT:
            return viewer is not None and is_in_covenant(viewer, owner)

        # -------------------------------------------------
        # 4️⃣ DEFAULT → follow profile privacy
        # -------------------------------------------------
        if is_profile_private(owner):
            return viewer is not None and are_friends(viewer, owner)

        return True

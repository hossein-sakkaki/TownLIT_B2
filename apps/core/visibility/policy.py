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
    def _viewer_or_none(viewer):
        # Normalize viewer for anonymous requests
        if not viewer:
            return None
        if getattr(viewer, "is_authenticated", False):
            return viewer
        return None

    @staticmethod
    def can_view(*, viewer, obj) -> bool:
        viewer = VisibilityPolicy._viewer_or_none(viewer)

        # 1) Moderation gates
        if not getattr(obj, "is_active", True) or getattr(obj, "is_hidden", False):
            return False

        # 2) Owner can always view
        if viewer and is_owner(viewer, obj):
            return True

        # 3) Explicit visibility
        if obj.visibility == VISIBILITY_PRIVATE:
            return False

        if obj.visibility == VISIBILITY_GLOBAL:
            return True

        owner = obj.content_object

        if obj.visibility == VISIBILITY_FRIENDS:
            return viewer is not None and are_friends(viewer, owner)

        if obj.visibility == VISIBILITY_COVENANT:
            return viewer is not None and is_in_covenant(viewer, owner)

        # 4) DEFAULT follows profile privacy
        if is_profile_private(owner):
            return viewer is not None and are_friends(viewer, owner)

        return True

    @staticmethod
    def gate_reason(*, viewer, obj) -> str | None:
        """
        Returns:
          - None: allowed
          - "hidden": inactive/hidden
          - "login_required": viewer is anonymous but might gain access by login
          - "forbidden": viewer is logged-in but not eligible
        """
        v = VisibilityPolicy._viewer_or_none(viewer)

        # Moderation gates: treat as hidden
        if not getattr(obj, "is_active", True) or getattr(obj, "is_hidden", False):
            return "hidden"

        # Allowed?
        if VisibilityPolicy.can_view(viewer=v or viewer, obj=obj):
            return None

        # Not allowed
        if v is None:
            return "login_required"

        return "forbidden"

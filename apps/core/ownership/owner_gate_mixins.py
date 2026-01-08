import logging
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework import status

from apps.core.ownership.owner_resolver import (
    resolve_owner_user_and_member
)

logger = logging.getLogger(__name__)


class OwnerGateMixin:
    """
    Reusable owner-based access gates.
    Designed for Moment / Testimony / Post / future content.
    """

    # -------------------------------------------------
    # HARD GATE (no redirect, no leak)
    # -------------------------------------------------
    def apply_hard_owner_gate(self, request, obj):
        """
        Hard concealment gate.
        Used for:
        - is_deleted
        - is_suspended
        - is_hidden_by_confidants

        Raises NotFound to behave like 404.
        """
        viewer = request.user if request.user.is_authenticated else None
        owner_user, owner_member, _ = resolve_owner_user_and_member(obj)

        if not owner_user:
            return

        # Owner himself can always view
        if viewer and viewer.is_authenticated and viewer.id == owner_user.id:
            return

        # 1) Deleted user
        if getattr(owner_user, "is_deleted", False):
            raise NotFound()

        # 2) Suspended user
        if getattr(owner_user, "is_suspended", False):
            raise NotFound()

        # 3) Hidden by confidants
        if owner_member and getattr(owner_member, "is_hidden_by_confidants", False):
            raise NotFound()


    # -------------------------------------------------
    # SOFT PROFILE REDIRECT GATE
    # -------------------------------------------------
    def apply_profile_privacy_gate(self, request, obj):
        """
        Soft gate for private profiles.
        Returns Response with profile_gate payload OR None.
        """
        viewer = request.user if request.user.is_authenticated else None
        owner_user, owner_member, _ = resolve_owner_user_and_member(obj)

        if not owner_user or not owner_member:
            return None

        if not getattr(owner_member, "is_privacy", False):
            return None

        # Owner himself can view
        if viewer and viewer.is_authenticated and viewer.id == owner_user.id:
            return None

        # Optional: friend check hook
        is_friend = False
        try:
            if hasattr(self, "_is_friend"):
                is_friend = self._is_friend(viewer, owner_user)
        except Exception:
            logger.exception("Friendship check failed")

        if is_friend:
            return None

        # 👇 soft redirect intent
        return Response(
            {
                "profile_gate": {
                    "key": "profile_privacy_redirect",
                    "reason": "private_profile",
                    "redirect_to": f"/lit/{owner_user.username}",
                }
            },
            status=status.HTTP_200_OK,
        )

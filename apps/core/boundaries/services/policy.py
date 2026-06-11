# apps/core/boundaries/services/policy.py

from __future__ import annotations

from django.db.models import Q

from apps.core.boundaries.constants import (
    BOUNDARY_STILLNESS,
    BOUNDARY_BOUNDARY,
)
from apps.core.boundaries.models import UserBoundary


class BoundaryPolicy:
    """
    Central policy for Stillness and Boundary.

    Rule summary:
    - Stillness affects only the owner's experience.
    - Boundary pauses direct interaction if it exists in either direction.
    - Never expose to target that they are in someone's Boundary.
    """

    @staticmethod
    def _valid_user(user) -> bool:
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and not getattr(user, "is_anonymous", False)
            and getattr(user, "id", None)
        )

    @staticmethod
    def _same_user(user1, user2) -> bool:
        return bool(
            user1
            and user2
            and getattr(user1, "id", None)
            and getattr(user2, "id", None)
            and user1.id == user2.id
        )

    @staticmethod
    def active_boundary_exists(*, owner, target, boundary_type: str) -> bool:
        if not BoundaryPolicy._valid_user(owner) or not BoundaryPolicy._valid_user(target):
            return False

        if BoundaryPolicy._same_user(owner, target):
            return False

        return UserBoundary.objects.filter(
            owner=owner,
            target=target,
            boundary_type=boundary_type,
            is_active=True,
        ).exists()

    @staticmethod
    def is_in_stillness(*, owner, target) -> bool:
        """
        True when owner placed target in Stillness.
        """
        return BoundaryPolicy.active_boundary_exists(
            owner=owner,
            target=target,
            boundary_type=BOUNDARY_STILLNESS,
        )

    @staticmethod
    def has_boundary(*, owner, target) -> bool:
        """
        True when owner placed target in Boundary.
        """
        return BoundaryPolicy.active_boundary_exists(
            owner=owner,
            target=target,
            boundary_type=BOUNDARY_BOUNDARY,
        )

    @staticmethod
    def has_boundary_between(user1, user2) -> bool:
        """
        True if either user has placed the other in Boundary.

        Direct interaction should be unavailable in both directions.
        """
        if not BoundaryPolicy._valid_user(user1) or not BoundaryPolicy._valid_user(user2):
            return False

        if BoundaryPolicy._same_user(user1, user2):
            return False

        return UserBoundary.objects.filter(
            is_active=True,
            boundary_type=BOUNDARY_BOUNDARY,
        ).filter(
            Q(owner=user1, target=user2)
            |
            Q(owner=user2, target=user1)
        ).exists()

    @staticmethod
    def has_any_peace_setting_between(user1, user2) -> bool:
        """
        True if Stillness or Boundary exists in either direction.
        Useful for suggestions/search ranking.
        """
        if not BoundaryPolicy._valid_user(user1) or not BoundaryPolicy._valid_user(user2):
            return False

        if BoundaryPolicy._same_user(user1, user2):
            return False

        return UserBoundary.objects.filter(
            is_active=True,
        ).filter(
            Q(owner=user1, target=user2)
            |
            Q(owner=user2, target=user1)
        ).exists()

    # ------------------------------------------------------------------
    # Direct interaction gates
    # ------------------------------------------------------------------

    @staticmethod
    def can_message(*, sender, recipient) -> bool:
        return not BoundaryPolicy.has_boundary_between(sender, recipient)

    @staticmethod
    def can_send_friend_request(*, sender, recipient) -> bool:
        return not BoundaryPolicy.has_boundary_between(sender, recipient)

    @staticmethod
    def can_send_fellowship_request(*, sender, recipient) -> bool:
        return not BoundaryPolicy.has_boundary_between(sender, recipient)

    @staticmethod
    def can_comment(*, actor, owner_user) -> bool:
        return not BoundaryPolicy.has_boundary_between(actor, owner_user)

    @staticmethod
    def can_react(*, actor, owner_user) -> bool:
        return not BoundaryPolicy.has_boundary_between(actor, owner_user)

    @staticmethod
    def can_mention(*, actor, target) -> bool:
        return not BoundaryPolicy.has_boundary_between(actor, target)

    # ------------------------------------------------------------------
    # Notification / feed / search gates
    # ------------------------------------------------------------------

    @staticmethod
    def can_notify(*, actor, recipient) -> bool:
        """
        Notification should not be created if:
        - recipient placed actor in Stillness
        - any Boundary exists between actor and recipient
        """
        if BoundaryPolicy.has_boundary_between(actor, recipient):
            return False

        if BoundaryPolicy.is_in_stillness(owner=recipient, target=actor):
            return False

        return True

    @staticmethod
    def should_hide_from_feed(*, viewer, owner_user) -> bool:
        """
        Used by stream/feed.

        Hide owner_user content from viewer if:
        - viewer placed owner_user in Stillness
        - Boundary exists between them
        """
        if not BoundaryPolicy._valid_user(viewer) or not BoundaryPolicy._valid_user(owner_user):
            return False

        if BoundaryPolicy._same_user(viewer, owner_user):
            return False

        if BoundaryPolicy.has_boundary_between(viewer, owner_user):
            return True

        if BoundaryPolicy.is_in_stillness(owner=viewer, target=owner_user):
            return True

        return False

    @staticmethod
    def should_hide_from_suggestions(*, viewer, candidate) -> bool:
        """
        People suggestions / friend suggestions / fellowship suggestions.
        """
        if not BoundaryPolicy._valid_user(viewer) or not BoundaryPolicy._valid_user(candidate):
            return False

        if BoundaryPolicy._same_user(viewer, candidate):
            return False

        return BoundaryPolicy.has_any_peace_setting_between(viewer, candidate)

    @staticmethod
    def should_disable_profile_actions(*, viewer, profile_user) -> bool:
        """
        UI/action gate. Profile can still be visible depending on visibility policy,
        but direct actions should be disabled if Boundary exists.
        """
        return BoundaryPolicy.has_boundary_between(viewer, profile_user)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @staticmethod
    def target_ids_in_stillness_for(owner) -> list[int]:
        if not BoundaryPolicy._valid_user(owner):
            return []

        return list(
            UserBoundary.objects.filter(
                owner=owner,
                boundary_type=BOUNDARY_STILLNESS,
                is_active=True,
            ).values_list("target_id", flat=True)
        )

    @staticmethod
    def target_ids_in_boundary_for(owner) -> list[int]:
        if not BoundaryPolicy._valid_user(owner):
            return []

        return list(
            UserBoundary.objects.filter(
                owner=owner,
                boundary_type=BOUNDARY_BOUNDARY,
                is_active=True,
            ).values_list("target_id", flat=True)
        )

    @staticmethod
    def user_ids_with_boundary_between(viewer) -> list[int]:
        if not BoundaryPolicy._valid_user(viewer):
            return []

        rows = UserBoundary.objects.filter(
            is_active=True,
            boundary_type=BOUNDARY_BOUNDARY,
        ).filter(
            Q(owner=viewer) | Q(target=viewer)
        ).values_list("owner_id", "target_id")

        ids = set()

        for owner_id, target_id in rows:
            if owner_id != viewer.id:
                ids.add(owner_id)
            if target_id != viewer.id:
                ids.add(target_id)

        return list(ids)

    @staticmethod
    def excluded_user_ids_for_suggestions(viewer) -> list[int]:
        """
        Exclude:
        - users viewer placed in Stillness
        - users viewer has Boundary with in either direction
        """
        if not BoundaryPolicy._valid_user(viewer):
            return []

        ids = set(BoundaryPolicy.target_ids_in_stillness_for(viewer))
        ids.update(BoundaryPolicy.user_ids_with_boundary_between(viewer))
        return list(ids)
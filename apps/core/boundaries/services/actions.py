# apps/core/boundaries/services/actions.py

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.core.boundaries.constants import (
    BOUNDARY_STILLNESS,
    BOUNDARY_BOUNDARY,
    BOUNDARY_SOURCE_PROFILE,
    BOUNDARY_SELF_ACTION_MESSAGE,
)
from apps.core.boundaries.models import UserBoundary


@dataclass(frozen=True)
class BoundaryCleanupResult:
    friendships_cleaned: int = 0
    fellowships_cleaned: int = 0

    @property
    def cleaned_any(self) -> bool:
        return self.friendships_cleaned > 0 or self.fellowships_cleaned > 0


class BoundaryActionService:
    """
    Write-side service for Stillness and Boundary.

    Important product rule:
    - Stillness does NOT remove relationships.
    - Boundary DOES remove active/pending Friendship and Fellowship relations
      between owner and target.

    Cleanup is intentionally quiet to avoid leaking Boundary state to the target.
    """

    @staticmethod
    def set_boundary(
        *,
        owner,
        target,
        boundary_type: str,
        source: str = BOUNDARY_SOURCE_PROFILE,
        reason: str = "",
        note: str = "",
    ) -> tuple[UserBoundary, BoundaryCleanupResult]:
        if not owner or not target:
            raise serializers.ValidationError({
                "error": "Owner and target are required."
            })

        if owner.id == target.id:
            raise serializers.ValidationError({
                "error": BOUNDARY_SELF_ACTION_MESSAGE,
                "code": "self_boundary_not_allowed",
            })

        if boundary_type not in {BOUNDARY_STILLNESS, BOUNDARY_BOUNDARY}:
            raise serializers.ValidationError({
                "error": "Invalid boundary type.",
                "code": "invalid_boundary_type",
            })

        with transaction.atomic():
            obj, created = UserBoundary.objects.select_for_update().get_or_create(
                owner=owner,
                target=target,
                boundary_type=boundary_type,
                defaults={
                    "source": source,
                    "reason": reason or "",
                    "note": note or "",
                    "is_active": True,
                },
            )

            if not created:
                obj.source = source or obj.source
                obj.reason = reason or obj.reason
                obj.note = note or obj.note
                obj.is_active = True
                obj.save(update_fields=[
                    "source",
                    "reason",
                    "note",
                    "is_active",
                    "updated_at",
                ])

            cleanup = BoundaryCleanupResult()

            # Boundary supersedes Stillness and also removes direct relationships.
            if boundary_type == BOUNDARY_BOUNDARY:
                UserBoundary.objects.filter(
                    owner=owner,
                    target=target,
                    boundary_type=BOUNDARY_STILLNESS,
                    is_active=True,
                ).update(is_active=False)

                cleanup = BoundaryActionService._cleanup_relationships_for_boundary(
                    owner=owner,
                    target=target,
                )

            return obj, cleanup

    @staticmethod
    def remove_boundary(
        *,
        owner,
        target,
        boundary_type: str,
    ) -> bool:
        if not owner or not target:
            raise serializers.ValidationError({
                "error": "Owner and target are required."
            })

        if owner.id == target.id:
            raise serializers.ValidationError({
                "error": BOUNDARY_SELF_ACTION_MESSAGE,
                "code": "self_boundary_not_allowed",
            })

        if boundary_type not in {BOUNDARY_STILLNESS, BOUNDARY_BOUNDARY}:
            raise serializers.ValidationError({
                "error": "Invalid boundary type.",
                "code": "invalid_boundary_type",
            })

        updated = UserBoundary.objects.filter(
            owner=owner,
            target=target,
            boundary_type=boundary_type,
            is_active=True,
        ).update(is_active=False)

        return updated > 0

    @staticmethod
    def _cleanup_relationships_for_boundary(*, owner, target) -> BoundaryCleanupResult:
        """
        Quietly remove Friendship and Fellowship relationships when Boundary is set.

        Why quiet?
        Boundary should not notify the target that they were bounded.

        Friendship:
        - accepted/pending active edges are set inactive.
        - accepted -> deleted
        - pending -> cancelled
        - other statuses -> deleted as defensive cleanup

        Fellowship:
        - pending/accepted rows in both directions are deleted quietly.
        - We do not save status='Cancelled' before delete here because that may trigger
          notification signals and leak the Boundary action.
        """
        friendships_cleaned = BoundaryActionService._cleanup_friendships_for_boundary(
            owner=owner,
            target=target,
        )

        fellowships_cleaned = BoundaryActionService._cleanup_fellowships_for_boundary(
            owner=owner,
            target=target,
        )

        return BoundaryCleanupResult(
            friendships_cleaned=friendships_cleaned,
            fellowships_cleaned=fellowships_cleaned,
        )

    @staticmethod
    def _cleanup_friendships_for_boundary(*, owner, target) -> int:
        """
        Quietly remove active Friendship rows between owner and target.

        Important:
        - Uses QuerySet.update(), not model.save().
        - This intentionally avoids post_save notification signals.
        - Boundary cleanup must not notify or reveal the Boundary action.

        Rules:
        - pending  -> cancelled + inactive
        - accepted/other active statuses -> deleted + inactive
        """
        from apps.profiles.models.relationships import Friendship

        base_qs = (
            Friendship.objects
            .filter(is_active=True)
            .filter(
                Q(from_user=owner, to_user=target)
                |
                Q(from_user=target, to_user=owner)
            )
        )

        now = timezone.now()

        pending_updated = (
            base_qs
            .filter(status="pending")
            .update(
                status="cancelled",
                is_active=False,
                deleted_at=now,
            )
        )

        non_pending_updated = (
            base_qs
            .exclude(status="pending")
            .update(
                status="deleted",
                is_active=False,
                deleted_at=now,
            )
        )

        return pending_updated + non_pending_updated

    @staticmethod
    def _cleanup_fellowships_for_boundary(*, owner, target) -> int:
        from apps.profiles.models.relationships import Fellowship

        qs = (
            Fellowship.objects
            .select_for_update()
            .filter(
                Q(from_user=owner, to_user=target)
                |
                Q(from_user=target, to_user=owner)
            )
            .filter(status__in=["Pending", "Accepted"])
        )

        ids = list(qs.values_list("id", flat=True))
        cleaned = len(ids)

        if cleaned:
            Fellowship.objects.filter(id__in=ids).delete()

        return cleaned
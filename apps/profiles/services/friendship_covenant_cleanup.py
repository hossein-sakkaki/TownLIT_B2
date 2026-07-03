# apps/profiles/services/friendship_covenant_cleanup.py

import logging
from dataclasses import dataclass
from typing import Optional

from django.db.models import Q

from apps.profiles.models.relationships import Fellowship

logger = logging.getLogger(__name__)


CONFIDANT_EDGE_TYPES = {"Confidant", "Entrusted"}


@dataclass(frozen=True)
class FriendshipCovenantCleanupResult:
    allowed: bool
    cleaned: bool = False
    cleaned_count: int = 0
    error: Optional[str] = None


def _litshield_is_active(user) -> bool:
    """
    Current backend source of truth for LITShield availability.
    In this codebase, fellowship visibility already relies on pin_security_enabled.
    """
    return bool(getattr(user, "pin_security_enabled", False))


def _relationship_type_for_viewer(fellowship: Fellowship, viewer) -> Optional[str]:
    """
    Returns the relationship type from the viewer's perspective.

    Example:
    - If viewer created Confidant, viewer sees Confidant.
    - If viewer is the reciprocal side, viewer sees reciprocal_fellowship_type.
    """
    if fellowship.from_user_id == viewer.id:
        return fellowship.fellowship_type

    if fellowship.to_user_id == viewer.id:
        return fellowship.reciprocal_fellowship_type

    return None


def _is_hidden_confidant_edge_for_viewer(
    *,
    fellowship: Fellowship,
    viewer,
    counterpart,
) -> bool:
    """
    Mirrors the fellowship_list visibility rules.

    Confidant:
      - Hidden when viewer's LITShield is inactive.

    Entrusted:
      - Hidden when the opposite user's LITShield is inactive.
      - This matches the current fellowship_list logic.
    """
    relationship_type = _relationship_type_for_viewer(fellowship, viewer)

    if relationship_type == "Confidant":
        return not _litshield_is_active(viewer)

    if relationship_type == "Entrusted":
        return not _litshield_is_active(counterpart)

    return False


def cleanup_hidden_confidant_fellowship_before_friendship_delete(
    *,
    initiator,
    counterpart,
) -> FriendshipCovenantCleanupResult:
    """
    Allows friendship deletion when the only blocking LITCovenant is a hidden
    Confidant/Entrusted relationship caused by inactive LITShield.

    Important:
    - Does NOT auto-delete Mentor/Pastor/Family covenant relationships.
    - Does NOT auto-delete visible Confidant relationships.
    - Deletes both symmetric Fellowship rows when cleanup is allowed.
    - Triggers exactly one fellowship cancellation notification by saving one row
      as Cancelled before deleting the pair.
    """
    fellowships = list(
        Fellowship.objects
        .select_for_update()
        .filter(
            Q(from_user=initiator, to_user=counterpart) |
            Q(from_user=counterpart, to_user=initiator),
            status="Accepted",
        )
        .select_related("from_user", "to_user")
    )

    if not fellowships:
        return FriendshipCovenantCleanupResult(
            allowed=True,
            cleaned=False,
            cleaned_count=0,
        )

    viewer_relationship_types = {
        _relationship_type_for_viewer(fellowship, initiator)
        for fellowship in fellowships
    }
    viewer_relationship_types.discard(None)

    # If there is any normal covenant relationship, do not auto-clean it.
    if not viewer_relationship_types.issubset(CONFIDANT_EDGE_TYPES):
        return FriendshipCovenantCleanupResult(
            allowed=False,
            cleaned=False,
            error=(
                "You cannot delete this friend while a LITCovenant relationship "
                "is active. Please remove the LITCovenant first."
            ),
        )

    hidden_edges = [
        fellowship
        for fellowship in fellowships
        if _is_hidden_confidant_edge_for_viewer(
            fellowship=fellowship,
            viewer=initiator,
            counterpart=counterpart,
        )
    ]

    # Confidant/Entrusted exists, but it is still visible/removable in LITCovenant.
    if not hidden_edges:
        return FriendshipCovenantCleanupResult(
            allowed=False,
            cleaned=False,
            error=(
                "You cannot delete this friend while a LITCovenant relationship "
                "is active. Please remove the LITCovenant first."
            ),
        )

    notifying = hidden_edges[0]

    # Trigger one notification burst, consistent with your current delete-fellowship flow.
    notifying.status = "Cancelled"
    notifying.save(update_fields=["status"])

    deleted_count = 0

    for fellowship in fellowships:
        fellowship.delete()
        deleted_count += 1

    return FriendshipCovenantCleanupResult(
        allowed=True,
        cleaned=True,
        cleaned_count=deleted_count,
    )
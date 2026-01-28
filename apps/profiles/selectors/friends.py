# apps/profiles/selectors/friends.py

from __future__ import annotations

from django.db.models import Q, F, Case, When, IntegerField
from apps.profiles.models import Friendship


def get_friend_user_ids(viewer) -> list[int]:
    """
    Returns CustomUser IDs of viewer's accepted friends.
    Works even if symmetric rows are not perfectly consistent.
    """
    if not viewer:
        return []

    qs = (
        Friendship.objects
        .filter(status="accepted", is_active=True)
        .filter(Q(from_user=viewer) | Q(to_user=viewer))
    )

    # Pick "the other side" user id for each row
    qs = qs.annotate(
        friend_id=Case(
            When(from_user=viewer, then=F("to_user_id")),
            default=F("from_user_id"),
            output_field=IntegerField(),
        )
    )

    return list(qs.values_list("friend_id", flat=True).distinct())

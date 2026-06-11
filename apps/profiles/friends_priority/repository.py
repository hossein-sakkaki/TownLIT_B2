# apps/profiles/friends_priority/repository.py

from __future__ import annotations

from typing import Set

from django.db.models import Q

from apps.accounts.models.user import CustomUser
from apps.profiles.models import Friendship


def friends_queryset_for(user: CustomUser):
    """
    Base friends queryset for profile friend blocks.

    Rules:
    - Accepted + active friendships only
    - Both endpoints must be active, non-deleted, and non-suspended
    - Return only visible counterpart users
    - Keep this queryset simple because service.py applies .only(...)
    """
    edges = (
        Friendship.objects
        .filter(
            Q(from_user=user) | Q(to_user=user),
            status="accepted",
            is_active=True,
        )
        .filter(
            from_user__is_active=True,
            from_user__is_deleted=False,
            from_user__is_suspended=False,
            to_user__is_active=True,
            to_user__is_deleted=False,
            to_user__is_suspended=False,
        )
        .values("from_user_id", "to_user_id")
    )

    counterpart_ids: Set[int] = set()
    uid = user.id

    for edge in edges:
        from_user_id = edge["from_user_id"]
        to_user_id = edge["to_user_id"]

        counterpart_id = to_user_id if from_user_id == uid else from_user_id
        counterpart_ids.add(counterpart_id)

    return (
        CustomUser.objects
        .filter(
            id__in=counterpart_ids,
            is_active=True,
            is_deleted=False,
            is_suspended=False,
        )
        .distinct()
    )
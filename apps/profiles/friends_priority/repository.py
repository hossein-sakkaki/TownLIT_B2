# apps/profiles/friends_priority/repository.py
from __future__ import annotations
from typing import Set

from django.db.models import Q

from apps.accounts.models import CustomUser
from apps.profiles.models import Friendship


def friends_queryset_for(user: CustomUser):
    """
    Base friends queryset (no ordering, no randomization).
    - Accepted + active
    - Both endpoints must be non-deleted
    - Unique counterpart users
    """
    edges = (
        Friendship.objects
        .filter(
            Q(from_user=user) | Q(to_user=user),
            status="accepted",
            is_active=True,
        )
        .filter(from_user__is_deleted=False, to_user__is_deleted=False)
        .values("from_user_id", "to_user_id")
    )

    counterpart_ids: Set[int] = set()
    uid = user.id

    for e in edges:
        fid, tid = e["from_user_id"], e["to_user_id"]
        counterpart_ids.add(tid if fid == uid else fid)

    return CustomUser.objects.filter(id__in=counterpart_ids, is_deleted=False)

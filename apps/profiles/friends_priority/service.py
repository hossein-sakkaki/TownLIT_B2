# apps/profiles/friends_priority/service.py

from __future__ import annotations
from typing import Optional, Sequence, List, Tuple

from django.db.models.functions import Lower

from apps.accounts.models import CustomUser
from apps.profiles.friends_priority.constants import is_default_avatar_value
from apps.profiles.friends_priority.engine import FriendPriorityEngine
from apps.profiles.friends_priority.journey import journey_weights_for
from apps.profiles.friends_priority.repository import friends_queryset_for
from apps.profiles.friends_priority.randomizer import randomized_friends_for_user


def _split_by_profile_image(
    friends_list: List[CustomUser],
) -> Tuple[List[CustomUser], List[CustomUser]]:
    """
    Deterministically split friends into:
    1) with custom profile image (NON-default)
    2) with default profile image

    ⚠️ NEVER touch image_name directly here.
    All normalization must go through is_default_avatar_value.
    """

    with_custom: List[CustomUser] = []
    with_default: List[CustomUser] = []

    for u in friends_list:
        avatar_value = getattr(u, "image_name", None)

        if is_default_avatar_value(avatar_value):
            with_default.append(u)
        else:
            with_custom.append(u)

    return with_custom, with_default


def get_friends_for_profile(
    user: CustomUser,
    *,
    random: bool = True,
    daily: bool = False,
    seed: Optional[str] = None,
    limit: Optional[int] = None,
):
    """
    Single public API for profile friends list.

    - random=False -> alphabetical
    - random=True  -> HARD + SOFT combined output:

      HARD (deterministic):
        1) friends with custom avatar first
        2) friends with default avatar after

      SOFT (weighted random) inside each group:
        - priority engine (future providers)
        - journey weights (future layer)
        - seedable / daily-stable randomizer

    ✅ Optimization:
    - friends fetched ONCE
    - engine providers can use friends_list (no DB hits)
    - randomizer uses friends_list (no DB hits)
    """
    base_qs = friends_queryset_for(user)

    if not random:
        qs = base_qs.annotate(username_lower=Lower("username")).order_by("username_lower")
        return qs[:limit] if isinstance(limit, int) and limit > 0 else qs

    # ✅ Fetch ONCE
    friends_list = list(base_qs.only("id", "username", "image_name"))

    # ✅ HARD RULE: deterministic grouping
    with_custom, with_default = _split_by_profile_image(friends_list)

    def _randomize_group(group: Sequence[CustomUser], *, group_seed_suffix: str, group_limit: Optional[int]):
        if not group:
            return []

        ids = [u.id for u in group if getattr(u, "id", None) is not None]
        if not ids:
            return []

        # SOFT providers (future) — currently may be empty until you add providers
        priority_weights = FriendPriorityEngine().build_weight_map(
            user,
            ids,
            friends_list=group,
        )

        # Journey layer (future)
        j_weights = journey_weights_for(user, ids)

        # Make deterministic but distinct streams per group (so the two groups don't "mirror" patterns)
        eff_seed = None
        if seed is not None:
            eff_seed = f"{seed}:{group_seed_suffix}"
        else:
            # keep None => fully random each request (unless daily=True handled in randomizer)
            eff_seed = None

        return randomized_friends_for_user(
            user,
            daily=daily,
            seed=eff_seed,
            limit=group_limit,
            priority_weight_map=priority_weights,
            journey_weight_map=j_weights,
            friends_list=group,
        )

    # Fill from custom-avatar group first
    first_limit = limit if isinstance(limit, int) and limit > 0 else None
    first_part = _randomize_group(with_custom, group_seed_suffix="custom_avatar", group_limit=first_limit)

    # Remaining capacity goes to default-avatar group
    remaining: Optional[int] = None
    if isinstance(limit, int) and limit > 0:
        remaining = max(limit - len(first_part), 0)

    second_part = []
    if remaining is None or remaining > 0:
        second_part = _randomize_group(with_default, group_seed_suffix="default_avatar", group_limit=remaining)

    combined = list(first_part) + list(second_part)
    return combined

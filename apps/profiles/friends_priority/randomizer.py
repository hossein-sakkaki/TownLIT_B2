# apps/profiles/friends_priority/randomizer.py
from __future__ import annotations
from typing import Dict, List, Optional, Sequence
import math
import random
from datetime import date

from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.profiles.friends_priority.repository import friends_queryset_for


def _daily_seed(base_seed: Optional[str]) -> str:
    today = timezone.localdate() if hasattr(timezone, "localdate") else date.today()
    return f"{today.strftime('%Y%m%d')}:{base_seed or ''}"


def _merge_multiply(*maps: Optional[Dict[int, float]]) -> Dict[int, float]:
    merged: Dict[int, float] = {}
    for m in maps:
        if not m:
            continue
        for uid, w in m.items():
            merged[uid] = merged.get(uid, 1.0) * float(w)
    return merged


def _weighted_sample_without_replacement(
    items: Sequence,
    weights: Dict[int, float],
    key_func=lambda x: x.id,
    rnd: Optional[random.Random] = None,
) -> List:
    """
    Efraimidis–Spirakis weighted random sampling without replacement.
    """
    rnd = rnd or random.Random()

    keys = []
    for it in items:
        iid = key_func(it)
        w = float(weights.get(iid, 1.0))
        if w <= 0:
            k = -math.inf
        else:
            u = rnd.random()
            k = u ** (1.0 / w)
        keys.append((k, it))

    keys.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in keys]


def randomized_friends_for_user(
    user: CustomUser,
    *,
    daily: bool = False,
    seed: Optional[str] = None,
    limit: Optional[int] = None,
    priority_weight_map: Optional[Dict[int, float]] = None,
    journey_weight_map: Optional[Dict[int, float]] = None,

    # ✅ NEW: allow passing already-fetched friends list to avoid double DB query
    friends_list: Optional[Sequence[CustomUser]] = None,
):
    """
    Randomize friends with layered weights (priority * journey).

    If friends_list is provided, we DO NOT hit DB again.
    """
    if friends_list is None:
        base_qs = friends_queryset_for(user).only("id", "username", "image_name")
        friends = list(base_qs)
    else:
        # trust caller: must contain CustomUser objects with id/username/image_name
        friends = list(friends_list)

    eff_seed = _daily_seed(seed) if daily else seed
    rnd = random.Random(eff_seed) if eff_seed is not None else random.Random()

    weights = _merge_multiply(priority_weight_map, journey_weight_map)

    ordered = _weighted_sample_without_replacement(
        friends, weights, key_func=lambda u: u.id, rnd=rnd
    )

    if isinstance(limit, int) and limit > 0:
        ordered = ordered[:limit]

    return ordered

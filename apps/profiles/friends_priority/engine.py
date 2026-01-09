# apps/profiles/friends_priority/engine.py

from __future__ import annotations
from typing import Dict, Iterable, List, Optional, Sequence

from apps.accounts.models import CustomUser
from apps.profiles.friends_priority.providers.base import FriendWeightProvider


def _merge_multiply(weight_maps: List[Dict[int, float]]) -> Dict[int, float]:
    """
    Merge multiple weight maps by multiplying weights:
      final_w = w1 * w2 * w3 ...

    Missing -> treated as 1.0
    """
    merged: Dict[int, float] = {}
    for m in weight_maps:
        for uid, w in m.items():
            merged[uid] = merged.get(uid, 1.0) * float(w)
    return merged


class FriendPriorityEngine:
    """
    Independent friend-priority engine (SOFT / weighted signals only).
    - DOES NOT include Hard rules (like profile image grouping).
    - DOES NOT include Journey logic (separate layer).

    ✅ Optimization:
    - Accept friends_list (already fetched) to avoid provider DB hits.
    """

    def __init__(self, providers: Optional[List[FriendWeightProvider]] = None):
        # IMPORTANT:
        # Hard rules (e.g. avatar updated) are handled in service.py via deterministic grouping.
        # So default providers here should be "soft signals" only.
        self.providers: List[FriendWeightProvider] = providers or []

    def build_weight_map(
        self,
        user: CustomUser,
        friend_ids: Iterable[int],
        *,
        friends_list: Optional[Sequence[CustomUser]] = None,
    ) -> Dict[int, float]:
        ids = list(friend_ids)
        if not ids or not self.providers:
            return {}

        friends_by_id: Optional[Dict[int, CustomUser]] = None
        if friends_list is not None:
            friends_by_id = {u.id: u for u in friends_list if getattr(u, "id", None) is not None}

        maps: List[Dict[int, float]] = []
        for p in self.providers:
            try:
                maps.append(p.weights(user, ids, friends_by_id=friends_by_id))
            except Exception:
                # fail-safe: never break profile response
                continue

        return _merge_multiply(maps)

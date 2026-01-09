# apps/profiles/friends_priority/journey.py
from __future__ import annotations
from typing import Dict, Iterable

from apps.accounts.models import CustomUser


def journey_weights_for(user: CustomUser, friend_ids: Iterable[int]) -> Dict[int, float]:
    """
    Journey weights (future).
    Kept here to avoid mixing with other helper concerns.
    """
    # TODO: implement when Journey launches
    return {}

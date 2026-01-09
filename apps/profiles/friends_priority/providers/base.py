from __future__ import annotations
from typing import Dict, Iterable, Optional, Protocol

from apps.accounts.models import CustomUser


class FriendWeightProvider(Protocol):
    """
    Provider contract for friend priority weights.

    Return mapping: {friend_id: weight}
    - weight > 1.0 boosts priority
    - weight = 1.0 neutral
    - weight < 1.0 demotes priority (optional)

    Note:
    - friends_by_id is optional. If provided, providers SHOULD use it to avoid DB hits.
    """

    code: str

    def weights(
        self,
        user: CustomUser,
        friend_ids: Iterable[int],
        *,
        friends_by_id: Optional[Dict[int, CustomUser]] = None,
    ) -> Dict[int, float]:
        ...

# apps/profiles/friends_priority/providers/profile_image.py

from __future__ import annotations
from typing import Dict, Iterable, Optional

from apps.accounts.models import CustomUser
from apps.profiles.friends_priority.providers.base import FriendWeightProvider
from apps.profiles.friends_priority.constants import is_default_avatar_value


class ProfileImageProvider(FriendWeightProvider):
    """
    Boost friends who have updated their profile image (not default).
    """

    code = "profile_image"

    def __init__(self, boost: float = 1.6):
        self.boost = float(boost)

    def weights(
        self,
        user: CustomUser,
        friend_ids: Iterable[int],
        *,
        friends_by_id: Optional[Dict[int, CustomUser]] = None,
    ) -> Dict[int, float]:
        ids = list(friend_ids)
        if not ids:
            return {}

        out: Dict[int, float] = {}

        # ✅ Prefer the already-fetched objects to avoid DB hits
        if friends_by_id:
            for fid in ids:
                u = friends_by_id.get(fid)
                if not u:
                    continue
                img = (getattr(u, "image_name", None) or "").strip()
                has_custom = not is_default_avatar_value(img)
                out[fid] = self.boost if has_custom else 1.0
            return out

        # Fallback (should be rare once service passes friends_list)
        qs = CustomUser.objects.filter(id__in=ids).only("id", "image_name")
        for u in qs:
            img = (getattr(u, "image_name", None) or "").strip()
            has_custom = not is_default_avatar_value(img)
            out[u.id] = self.boost if has_custom else 1.0

        return out

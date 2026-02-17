# apps/subtitles/services/gender_resolver.py

from __future__ import annotations
from typing import Optional
from apps.accounts.constants import MALE, FEMALE

def resolve_owner_gender_from_content(obj) -> Optional[str]:
    """
    Best-effort resolve gender from your canonical owner models.
    Returns "Male" | "Female" | None
    """
    if not obj:
        return None

    # Case A) object has "owner" or "user" directly
    user = getattr(obj, "user", None)
    if user and getattr(user, "gender", None) in (MALE, FEMALE):
        return user.gender

    owner = getattr(obj, "owner", None)
    if owner:
        user2 = getattr(owner, "user", None) or getattr(owner, "user_account", None)
        if user2 and getattr(user2, "gender", None) in (MALE, FEMALE):
            return user2.gender

    # Case B) your pattern: obj.content_object (Member/Org/Guest) -> .user
    owner2 = getattr(obj, "content_object", None)
    if owner2:
        user3 = getattr(owner2, "user", None)
        if user3 and getattr(user3, "gender", None) in (MALE, FEMALE):
            return user3.gender

    # Case C) fallback: obj.created_by / obj.author (common patterns)
    for attr in ("created_by", "author"):
        u = getattr(obj, attr, None)
        if u and getattr(u, "gender", None) in (MALE, FEMALE):
            return u.gender

    return None

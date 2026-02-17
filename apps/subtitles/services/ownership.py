# apps/subtitles/services/ownership.py

from __future__ import annotations

from apps.accounts.constants import MALE, FEMALE


def resolve_owner_gender_from_transcript(transcript) -> str:
    """
    Returns: "Male" | "Female" | "" (never None)
    Best-effort based on transcript.content_object ownership shapes.
    """
    try:
        obj = getattr(transcript, "content_object", None)
        if not obj:
            return ""

        # 1) Direct user on object
        user = getattr(obj, "user", None)
        if user and getattr(user, "gender", "") in (MALE, FEMALE):
            return user.gender

        # 2) Common owner pointers
        for owner_attr in ("owner", "member", "created_by", "author", "content_object"):
            owner = getattr(obj, owner_attr, None)
            if not owner:
                continue

            # owner might be CustomUser
            if getattr(owner, "gender", "") in (MALE, FEMALE):
                return owner.gender

            # owner might wrap CustomUser
            u = getattr(owner, "user", None)
            if u and getattr(u, "gender", "") in (MALE, FEMALE):
                return u.gender

        return ""
    except Exception:
        return ""

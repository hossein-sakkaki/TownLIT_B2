# apps/profiles/helpers.py
from __future__ import annotations

from typing import Set

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from apps.accounts.models import CustomUser, SocialMediaLink
from apps.profiles.models import Member, Fellowship

# Optional: only if you still use this helper in other places
from apps.posts.models.testimony import Testimony


# --------------------------------------------------------------
# (Optional) Testimonies helper (kept for future algorithms)
# --------------------------------------------------------------
VISIBLE_FILTERS = dict(is_active=True, is_hidden=False, is_restricted=False, is_suspended=False)


def testimonies_for_member(member: Member):
    """
    Return latest testimony per type for a member (audio/video/written).
    Kept here because it is NOT part of friends_priority engine.
    """
    ct = ContentType.objects.get_for_model(member.__class__)
    base_qs = (
        Testimony.objects
        .filter(content_type=ct, object_id=member.id, **VISIBLE_FILTERS)
    )

    by_type = {"audio": None, "video": None, "written": None}

    for t in (Testimony.TYPE_AUDIO, Testimony.TYPE_VIDEO, Testimony.TYPE_WRITTEN):
        inst = (
            base_qs.filter(type=t)
            .order_by("-published_at", "-updated_at", "-id")
            .first()
        )
        by_type[t] = inst

    return by_type


# -----------------------------
# Social links for a user
# -----------------------------
def social_links_for_user(user: CustomUser):
    """
    Generic FK: content_object = CustomUser
    """
    ct = ContentType.objects.get_for_model(type(user))
    return (
        SocialMediaLink.objects
        .filter(content_type=ct, object_id=user.id, is_active=True)
        .select_related("social_media_type")
        .order_by("id")
    )


# -----------------------------
# Fellowships visibility policy
# -----------------------------
def fellowships_visible(member: Member):
    """
    Apply visibility rules similar to MemberSerializer logic:
    - respect member.show_fellowship_in_profile
    - respect hide_confidants & pin flags
    """
    if not getattr(member, "show_fellowship_in_profile", False):
        return Fellowship.objects.none()

    user = member.user
    qs = (
        Fellowship.objects
        .filter(Q(from_user=user) | Q(to_user=user), status="Accepted")
        .select_related(
            "from_user",
            "to_user",
            "from_user__member_profile",
            "to_user__member_profile",
        )
    )

    hide_confidants = bool(getattr(member, "hide_confidants", False))
    out_ids: list[int] = []
    seen: Set[tuple[int, str]] = set()

    for f in qs:
        if f.from_user_id == user.id:
            rel_type = f.fellowship_type
            opposite_user = f.to_user
        else:
            rel_type = f.reciprocal_fellowship_type
            opposite_user = f.from_user

        if hide_confidants and rel_type == "Confidant":
            continue
        if rel_type == "Confidant" and not getattr(user, "pin_security_enabled", False):
            continue
        if rel_type == "Entrusted" and not getattr(opposite_user, "pin_security_enabled", False):
            continue

        key = (opposite_user.id, rel_type)
        if key in seen:
            continue
        seen.add(key)
        out_ids.append(f.id)

    return Fellowship.objects.filter(id__in=out_ids)


# -----------------------------
# Small text helpers
# -----------------------------
ACRONYMS = {"it", "ai", "tv"}  # extend if needed


def humanize_service_code(code: str) -> str:
    """Title-case with acronym preservation; fallback if no display label found."""
    if not code:
        return ""
    s = code.replace("_", " ").strip()
    parts = []
    for p in s.split():
        lp = p.lower()
        parts.append(lp.upper() if lp in ACRONYMS else (p[:1].upper() + p[1:].lower()))
    return " ".join(parts)

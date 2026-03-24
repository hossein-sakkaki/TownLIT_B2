# apps/profiles/helpers/fellowships.py

from __future__ import annotations

from typing import Set

from django.db.models import Q

from apps.profiles.models.member import Member
from apps.profiles.models.relationships import Fellowship


def fellowships_visible(member: Member):
    """
    Apply visibility rules similar to MemberSerializer logic.
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
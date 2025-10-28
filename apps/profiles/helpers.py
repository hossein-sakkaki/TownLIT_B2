# apps/profiles/helpers.py
from __future__ import annotations
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import math
import random
from datetime import date

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from django.contrib.contenttypes.models import ContentType
from apps.posts.models import Testimony
from apps.accounts.models import CustomUser, SocialMediaLink
from apps.profiles.models import Member, Fellowship, Friendship



# --------------------------------------------------------------
VISIBLE_FILTERS = dict(is_active=True, is_hidden=False, is_restricted=False, is_suspended=False)

def testimonies_for_member(member):
    """
    {
      'audio':   Testimony|None,
      'video':   Testimony|None,
      'written': Testimony|None,
    }
    """
    ct = ContentType.objects.get_for_model(member.__class__)  # امن‌تر از type(member)
    base_qs = (Testimony.objects
               .filter(content_type=ct, object_id=member.id, **VISIBLE_FILTERS))

    by_type = {'audio': None, 'video': None, 'written': None}
    # به‌صورت پیش‌فرض یکی از هر نوع داریم (Constraint شما)، پس first() کافیست.
    for t in (Testimony.TYPE_AUDIO, Testimony.TYPE_VIDEO, Testimony.TYPE_WRITTEN):
        inst = base_qs.filter(type=t).order_by('-published_at', '-updated_at', '-id').first()
        by_type[t] = inst
    return by_type


# -----------------------------
# Core friends retrieval (no random)
# -----------------------------
def friends_queryset_for(user: CustomUser):
    """
    Return a base queryset of friends (CustomUser) for a user.
    - Accepted + active
    - Both endpoints must be non-deleted
    - Unique counterpart users
    """
    edges = (
        Friendship.objects
        .filter(
            Q(from_user=user) | Q(to_user=user),
            status="accepted",
            is_active=True,
        )
        .filter(from_user__is_deleted=False, to_user__is_deleted=False)
        .values("from_user_id", "to_user_id")
    )

    counterpart_ids = set()
    uid = user.id
    for e in edges:
        fid, tid = e["from_user_id"], e["to_user_id"]
        counterpart_ids.add(tid if fid == uid else fid)

    return CustomUser.objects.filter(id__in=counterpart_ids, is_deleted=False)


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
            "from_user", "to_user",
            "from_user__member_profile", "to_user__member_profile"
        )
    )

    hide_confidants = bool(getattr(member, "hide_confidants", False))
    out_ids, seen = [], set()

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
# Randomization + weighting
# -----------------------------
def _daily_seed(base_seed: Optional[str]) -> str:
    """
    Compose a daily seed based on current date (YYYYMMDD) + optional base seed.
    """
    today = timezone.localdate() if hasattr(timezone, "localdate") else date.today()
    daily = today.strftime("%Y%m%d")
    return f"{daily}:{base_seed or ''}"


def _weighted_sample_without_replacement(
    items: Sequence,
    weights: Dict[int, float],
    key_func=lambda x: x.id,
    rnd: Optional[random.Random] = None,
) -> List:
    """
    Efraimidis–Spirakis weighted random sampling without replacement.
    - items: sequence of objects
    - weights: mapping id -> weight (>0). Missing -> weight=1.0
    - key_func: get stable id for each item
    - rnd: random.Random instance (deterministic if seeded)
    """
    if rnd is None:
        rnd = random.Random()

    keys = []
    for it in items:
        iid = key_func(it)
        w = float(weights.get(iid, 1.0))
        if w <= 0:
            # Zero/negative weight → effectively send to the end
            k = -math.inf
        else:
            u = rnd.random()  # (0,1)
            # Key = u^(1/w) -> larger key ≈ higher chance
            k = u ** (1.0 / w)          
        keys.append((k, it))

    # Sort descending by key
    keys.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in keys]


def randomized_friends_for_member(
    user: CustomUser,
    *,
    daily: bool = False,
    seed: Optional[str] = None,
    limit: Optional[int] = None,
    journey_weight_map: Optional[Dict[int, float]] = None,
):
    """
    Randomize friends with optional deterministic behavior:
    - daily=True  -> stable within the same date
    - seed given  -> stable across requests
    - both off    -> different order on each request
    """
    base_qs = friends_queryset_for(user).only("id", "username", "image_name")
    friends = list(base_qs)

    # --- choose effective seed ---
    # daily has priority to make a per-day-stable sequence (if enabled)
    eff_seed: Optional[str]
    if daily:
        eff_seed = _daily_seed(seed)  # e.g., "20251019:myseed" or "20251019:"
    else:
        eff_seed = seed  # may be None

    # --- choose RNG instance ---
    if eff_seed is None:
        rnd = random.Random()  # no seed => different each request
    else:
        rnd = random.Random(eff_seed)  # deterministic

    # build weights (future: Journey)
    weights: Dict[int, float] = {}
    if journey_weight_map:
        weights.update(journey_weight_map)

    ordered = _weighted_sample_without_replacement(
        friends, weights, key_func=lambda u: u.id, rnd=rnd
    )

    if isinstance(limit, int) and limit > 0:
        ordered = ordered[:limit]

    return ordered


# -----------------------------
# Future: Journey weights (stub)
# -----------------------------
def journey_weights_for(user: CustomUser, friend_ids: Iterable[int]) -> Dict[int, float]:
    """
    Placeholder for future Journey-based prioritization.
    - Return {friend_id: weight} with weight>1 boosting priority.
    - Currently returns {} (equal weights).
    """
    # TODO: when Journey is implemented, compute participation and produce weights.
    return {}


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
# apps/friendship/services/listing.py
from django.db.models import Q, F
from ..models import Friendship
from .params import resolve_randomization_params
from .randomization import make_day_seed, shuffle_list
from .priority import apply_priority_modules

def fetch_unique_friends(user):
    qs = (
        Friendship.objects
        .filter(Q(from_user=user) | Q(to_user=user), status="accepted")
        .filter(Q(from_user__id__lt=F("to_user__id")))
        .select_related("from_user", "to_user")
    )
    friends = []
    for fr in qs:
        friends.append(fr.to_user if fr.from_user == user else fr.from_user)
    return friends

def build_friends_list(user, query_params):
    """pipeline: priority -> randomize -> limit"""
    params = resolve_randomization_params(query_params)
    friends = fetch_unique_friends(user)

    # 1) priority (آینده)
    friends = apply_priority_modules(friends)

    # 2) randomize
    if params["random"]:
        seed = params["seed"]
        if params["daily"] and not seed:
            seed = make_day_seed()
        friends = shuffle_list(friends, seed=seed)

    # 3) limit
    if params["limit"] is not None:
        friends = friends[: params["limit"]]

    meta = {
        "count_total": len(friends),
        "randomized": bool(params["random"]),
        "daily": bool(params["daily"]),
        "seed_used": (make_day_seed() if params["daily"] and not params["seed"] else params["seed"]),
        "limit": params["limit"],
    }
    return friends, meta

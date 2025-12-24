# apps/sanctuary/services/ownership.py

from typing import Callable, Dict, Iterable, Set
from django.contrib.contenttypes.models import ContentType

# Resolver signature: given obj -> set of user_ids who are considered "owners/admins"
OwnerResolver = Callable[[object], Set[int]]

# Registry by (app_label, model_name)
_OWNER_RESOLVERS: Dict[str, OwnerResolver] = {}


# def _key_for_obj(obj) -> str:
#     ct = ContentType.objects.get_for_model(obj.__class__)
#     return f"{ct.app_label}.{ct.model}"

def _key_for_obj(obj) -> str:
    m = obj.__class__._meta
    return f"{m.app_label}.{m.model_name}"


def register_owner_resolver(app_label: str, model: str, resolver: OwnerResolver):
    """
    Register a custom owner resolver for a model.
    Example key: "posts.moment" or "profilesorg.organization"
    """
    _OWNER_RESOLVERS[f"{app_label}.{model}"] = resolver


def get_owner_user_ids(target_obj) -> Set[int]:
    """
    Returns a set of user IDs considered owners/admins of the target.
    Falls back to heuristics if no resolver is registered.
    """
    if not target_obj:
        return set()

    key = _key_for_obj(target_obj)

    # 1) Custom resolver (best)
    resolver = _OWNER_RESOLVERS.get(key)
    if resolver:
        try:
            return set(resolver(target_obj) or set())
        except Exception:
            return set()

    # 2) Heuristic fallback (safe + minimal assumptions)
    ids: Set[int] = set()

    # Common single-owner relations
    for attr in ["user", "owner", "created_by", "author", "publisher"]:
        u = getattr(target_obj, attr, None)
        uid = getattr(u, "id", None)
        if uid:
            ids.add(uid)

    # Common many-owner relations (organizations, teams)
    for attr in ["owners", "org_owners", "admins", "moderators"]:
        rel = getattr(target_obj, attr, None)
        if rel is None:
            continue

        # ManyToMany manager typically has .values_list
        try:
            ids.update(set(rel.values_list("id", flat=True)))
        except Exception:
            pass

    # Optional: group admin pattern (if your group model has a method)
    # Example: Dialogue.get_admin_ids()
    if hasattr(target_obj, "get_admin_ids"):
        try:
            ids.update(set(target_obj.get_admin_ids() or []))
        except Exception:
            pass

    return ids


# -------------------------------------------------------------------
# OPTIONAL: register your known models (recommended)
# Put these in AppConfig.ready() instead of importing here in prod.
# -------------------------------------------------------------------

def register_default_resolvers():
    """
    Call this from apps.sanctuary.apps.SanctuaryConfig.ready()
    to avoid import side effects.
    """

    # Example: Organization -> org_owners
    def org_resolver(org) -> Set[int]:
        try:
            return set(org.org_owners.values_list("id", flat=True))
        except Exception:
            return set()

    register_owner_resolver("profilesorg", "organization", org_resolver)

    # Example: Dialogue/Group -> admins (adjust to your real group model)
    # register_owner_resolver("conversation", "dialogue", lambda d: set(d.admins.values_list("id", flat=True)))

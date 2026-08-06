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
    for attr in ("owners", "org_owners", "admins", "moderators"):
        rel = getattr(target_obj, attr, None)
        if rel is None:
            continue

        try:
            related_model = rel.model
            field_names = {field.name for field in related_model._meta.get_fields()}

            if "user" in field_names:
                values = rel.values_list("user_id", flat=True)
            else:
                values = rel.values_list("id", flat=True)

            ids.update(int(value) for value in values if value)
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
    def org_resolver(org) -> Set[int]:
        user_ids: Set[int] = set()

        try:
            user_ids.update(
                org.org_owners.filter(is_active=True)
                .values_list("user_id", flat=True)
            )
        except Exception:
            pass

        try:
            user_ids.update(
                org.admin_relationships.filter(
                    is_approved=True,
                    member__is_active=True,
                ).values_list("member__user_id", flat=True)
            )
        except Exception:
            pass

        return {int(user_id) for user_id in user_ids if user_id}

    register_owner_resolver(
        "profilesOrg",
        "organization",
        org_resolver,
    )
# apps/sanctuary/services/appeal_access.py

from typing import Set
from rest_framework.exceptions import PermissionDenied

from apps.sanctuary.services.ownership import get_owner_user_ids


# Toggle if staff should always be allowed (optional)
ALLOW_STAFF_OVERRIDE = True


# Get requesters for all linked SanctuaryRequests ---------------------------------------------
def _get_requester_user_ids(outcome) -> Set[int]:
    """
    Collect requesters for all linked SanctuaryRequests.
    """
    ids: Set[int] = set()

    try:
        for req in outcome.sanctuary_requests.all():
            if req.requester_id:
                ids.add(req.requester_id)
    except Exception:
        pass

    return ids


# Check if user is allowed to appeal this outcome ---------------------------------------------
def can_user_appeal(outcome, user) -> bool:
    """
    True if user is allowed to appeal this outcome:
    - requester of any linked request
    - owner/admin of the reported target
    - optionally staff
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if ALLOW_STAFF_OVERRIDE and getattr(user, "is_staff", False):
        return True

    requester_ids = _get_requester_user_ids(outcome)

    # Reported target is outcome.content_object (Generic)
    target_obj = getattr(outcome, "content_object", None)
    owner_ids = get_owner_user_ids(target_obj)

    return (user.id in requester_ids) or (user.id in owner_ids)


# Assert if user is allowed to appeal this outcome ---------------------------------------------
def assert_can_appeal(outcome, user):
    """
    Raise if user is not allowed to appeal.
    """
    if not can_user_appeal(outcome, user):
        raise PermissionDenied("You are not allowed to appeal this Sanctuary outcome.")

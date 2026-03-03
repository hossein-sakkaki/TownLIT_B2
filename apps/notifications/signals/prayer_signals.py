# apps/notifications/signals/prayer_signals.py

import logging
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.posts.models.pray import Prayer, PrayerResponse, PrayerStatus
from apps.profiles.models import Friendship, Member
from apps.profiles.constants import ACCEPTED
from apps.notifications.services.services import create_and_dispatch_notification
from apps.core.visibility.constants import (
    VISIBILITY_PRIVATE,
    VISIBILITY_FRIENDS,
    VISIBILITY_COVENANT,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------
# Owner resolver
# ---------------------------------------------------------
def _get_owner_user(prayer: Prayer):
    obj = getattr(prayer, "content_object", None)
    if not obj:
        return None

    try:
        if isinstance(obj, Member):
            return obj.user
        if hasattr(obj, "user"):
            return obj.user
        if isinstance(obj, User):
            return obj
    except Exception:
        logger.exception("[Notif][Prayer] owner resolve failed")

    return None


# ---------------------------------------------------------
# Friends resolver (accepted only)
# ---------------------------------------------------------
def _get_accepted_friends(user):
    qs = (
        Friendship.objects
        .filter(status=ACCEPTED, is_active=True)
        .filter(Q(from_user=user) | Q(to_user=user))
    )

    friend_ids = []
    for f in qs:
        friend_ids.append(f.to_user_id if f.from_user_id == user.id else f.from_user_id)

    return User.objects.filter(id__in=friend_ids, is_active=True)


# ---------------------------------------------------------
# Link builder (profile scope, Moment-compatible)
# ---------------------------------------------------------
def _build_prayer_link(prayer: Prayer) -> str:
    """
    Build PROFILE-scope deep-link like Moment.
    """
    owner_user = _get_owner_user(prayer)
    username = getattr(owner_user, "username", None) or "user"

    # KeyPath for profile smart viewer
    k_param = "prayers.video" if getattr(prayer, "video", None) else "prayers.image"

    entry_path = "/profiles/members/profile"
    e_param = quote(entry_path, safe="")

    u = quote(username, safe="")
    base_path = f"/lit/{u}/content/{u}"

    focus_param = quote(f"prayer:{prayer.slug}", safe="")

    query_parts = [
        "type=media",
        f"e={e_param}",
        "s=profile",
        f"k={k_param}",
        "o=user",
        f"focus={focus_param}",
        "a=auto",
        "p=1",
    ]

    return f"{base_path}?{'&'.join(query_parts)}"


# ---------------------------------------------------------
# Type + message
# ---------------------------------------------------------
def _classify_kind(prayer: Prayer) -> str:
    return "video" if getattr(prayer, "video", None) else "image"


def _pick_new_prayer_type(kind: str) -> str:
    return "new_prayer_video" if kind == "video" else "new_prayer_image"


def _build_new_prayer_message(author, kind: str) -> str:
    username = getattr(author, "username", "Someone")
    # Keep same text for both kinds (simple + consistent)
    return f"{username} shared a prayer request — join in prayer 🤍"


def _build_prayer_result_message(author, result_status: str) -> tuple[str, str]:
    username = getattr(author, "username", "Someone")

    if result_status == PrayerStatus.ANSWERED:
        return ("prayer_result_answered", f"{username} posted an update — praise report 🙏✨")

    return ("prayer_result_not_answered", f"{username} posted an update — please continue in support 🤍")


# ---------------------------------------------------------
# Public entry: Prayer available
# ---------------------------------------------------------
def notify_prayer_ready(prayer: Prayer) -> None:
    """
    Send notifications when a Prayer is fully available.
    Called by Prayer.on_available().
    """
    # Domain guard
    if not prayer or not prayer.is_available():
        return

    # Moderation guards
    if not getattr(prayer, "is_active", True) or getattr(prayer, "is_hidden", False) or getattr(prayer, "is_suspended", False):
        return

    # Private never notify
    if getattr(prayer, "visibility", None) == VISIBILITY_PRIVATE:
        return

    owner_user = _get_owner_user(prayer)
    if not owner_user:
        return

    # Recipients (friends only for now)
    if getattr(prayer, "visibility", None) in (VISIBILITY_FRIENDS, VISIBILITY_COVENANT):
        recipients = _get_accepted_friends(owner_user)
    else:
        recipients = _get_accepted_friends(owner_user)

    if not recipients.exists():
        return

    kind = _classify_kind(prayer)
    notif_type = _pick_new_prayer_type(kind)
    message = _build_new_prayer_message(owner_user, kind)
    link = _build_prayer_link(prayer)

    for recipient in recipients:
        if recipient.id == owner_user.id:
            continue

        create_and_dispatch_notification(
            recipient=recipient,
            actor=owner_user,
            notif_type=notif_type,
            message=message,
            target_obj=prayer,
            action_obj=None,
            link=link,
            extra_payload={
                "prayer_id": prayer.id,
                "kind": kind,
            },
        )


# ---------------------------------------------------------
# Public entry: PrayerResponse available
# ---------------------------------------------------------
def notify_prayer_result_ready(prayer: Prayer, response: PrayerResponse) -> None:
    """
    Send notifications when a PrayerResponse is fully available.
    Called by PrayerResponse.on_available().
    """
    if not prayer or not response:
        return

    # Domain guard
    if not response.is_available():
        return

    # Parent guards
    if not getattr(prayer, "is_active", True) or getattr(prayer, "is_hidden", False) or getattr(prayer, "is_suspended", False):
        return

    if getattr(prayer, "visibility", None) == VISIBILITY_PRIVATE:
        return

    owner_user = _get_owner_user(prayer)
    if not owner_user:
        return

    recipients = _get_accepted_friends(owner_user)
    if not recipients.exists():
        return

    notif_type, message = _build_prayer_result_message(owner_user, getattr(response, "result_status", ""))
    link = _build_prayer_link(prayer)

    for recipient in recipients:
        if recipient.id == owner_user.id:
            continue

        create_and_dispatch_notification(
            recipient=recipient,
            actor=owner_user,
            notif_type=notif_type,
            message=message,
            target_obj=prayer,
            action_obj=response,
            link=link,
            extra_payload={
                "prayer_id": prayer.id,
                "response_id": response.id,
                "result_status": response.result_status,
            },
        )
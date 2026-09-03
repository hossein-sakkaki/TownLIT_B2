# apps/notifications/signals/prayer_signals.py

import logging
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.core.visibility.constants import (
    VISIBILITY_COVENANT,
    VISIBILITY_FRIENDS,
    VISIBILITY_PRIVATE,
)
from apps.notifications.services.presentation import build_prayer_message
from apps.notifications.services.services import create_and_dispatch_notification
from apps.posts.models.pray import Prayer, PrayerResponse, PrayerStatus
from apps.profiles.constants import ACCEPTED
from apps.profiles.models import Friendship, Member

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_owner_user(prayer: Prayer):
    """Resolve the CustomUser that owns a Prayer."""
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
        logger.exception(
            "[Notif][Prayer] owner resolve failed"
        )

    return None


def _get_accepted_friends(user):
    """Return active accepted friends."""
    friendships = (
        Friendship.objects
        .filter(status=ACCEPTED, is_active=True)
        .filter(Q(from_user=user) | Q(to_user=user))
    )

    friend_ids = []

    for friendship in friendships:
        friend_ids.append(
            friendship.to_user_id
            if friendship.from_user_id == user.id
            else friendship.from_user_id
        )

    return User.objects.filter(
        id__in=friend_ids,
        is_active=True,
    )


def _build_prayer_link(prayer: Prayer) -> str:
    """Build a profile-scoped Prayer deep link."""
    owner_user = _get_owner_user(prayer)
    username = getattr(owner_user, "username", None) or "user"

    k_param = (
        "prayers.video"
        if getattr(prayer, "video", None)
        else "prayers.image"
    )

    entry_path = "/profiles/members/profile"
    e_param = quote(entry_path, safe="")
    u = quote(username, safe="")
    focus_param = quote(f"prayer:{prayer.slug}", safe="")

    base_path = f"/lit/{u}/content/{u}"

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


def _classify_kind(prayer: Prayer) -> str:
    return "video" if getattr(prayer, "video", None) else "image"


def _pick_new_prayer_type(kind: str) -> str:
    return "new_prayer_video" if kind == "video" else "new_prayer_image"


def _build_new_prayer_message(author, kind: str) -> str:
    event = "new_video" if kind == "video" else "new_image"
    return build_prayer_message(author, event)


def _build_prayer_result_message(
    author,
    result_status: str,
) -> tuple[str, str]:
    if result_status == PrayerStatus.ANSWERED:
        return (
            "prayer_result_answered",
            build_prayer_message(author, "answered"),
        )

    return (
        "prayer_result_not_answered",
        build_prayer_message(author, "follow_up"),
    )


def notify_prayer_ready(prayer: Prayer) -> None:
    """
    Send notifications when a Prayer is fully available.

    Called by Prayer.on_available().
    """
    if not prayer or not prayer.is_available():
        return

    if (
        not getattr(prayer, "is_active", True)
        or getattr(prayer, "is_hidden", False)
        or getattr(prayer, "is_suspended", False)
    ):
        return

    if getattr(prayer, "visibility", None) == VISIBILITY_PRIVATE:
        return

    owner_user = _get_owner_user(prayer)
    if not owner_user:
        return

    # Friends are currently the notification audience for all supported
    # non-private Prayer visibility modes.
    if getattr(prayer, "visibility", None) in (
        VISIBILITY_FRIENDS,
        VISIBILITY_COVENANT,
    ):
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


def notify_prayer_result_ready(
    prayer: Prayer,
    response: PrayerResponse,
) -> None:
    """
    Send notifications when a PrayerResponse is fully available.

    Called by PrayerResponse.on_available().
    """
    if not prayer or not response:
        return

    if not response.is_available():
        return

    if (
        not getattr(prayer, "is_active", True)
        or getattr(prayer, "is_hidden", False)
        or getattr(prayer, "is_suspended", False)
    ):
        return

    if getattr(prayer, "visibility", None) == VISIBILITY_PRIVATE:
        return

    owner_user = _get_owner_user(prayer)
    if not owner_user:
        return

    recipients = _get_accepted_friends(owner_user)
    if not recipients.exists():
        return

    notif_type, message = _build_prayer_result_message(
        owner_user,
        getattr(response, "result_status", ""),
    )

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
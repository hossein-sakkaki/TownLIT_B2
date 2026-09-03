# apps/notifications/signals/testimony_signals.py

import logging
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.accounts.models.user import CustomUser
from apps.notifications.services.presentation import build_testimony_message
from apps.notifications.services.services import create_and_dispatch_notification
from apps.posts.models.testimony import Testimony
from apps.profiles.constants import ACCEPTED
from apps.profiles.models import Friendship

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_accepted_friends(user: CustomUser):
    """
    Return active users with an accepted friendship relationship.
    """
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


def _get_owner_user(instance: Testimony) -> CustomUser | None:
    """
    Resolve the CustomUser that owns a Testimony.

    Supported ownership:
    - Member -> Member.user
    - object.user -> CustomUser
    - direct CustomUser
    """
    obj = instance.content_object
    if not obj:
        return None

    try:
        # Local import avoids unnecessary model coupling at module load time.
        from apps.profiles.models import Member

        if isinstance(obj, Member) and isinstance(obj.user, CustomUser):
            return obj.user

        if hasattr(obj, "user") and isinstance(obj.user, CustomUser):
            return obj.user

        if isinstance(obj, CustomUser):
            return obj

    except Exception as error:
        logger.warning(
            "[Notif][Testimony] Failed to resolve owner user "
            "for testimony %s: %s",
            getattr(instance, "id", None),
            error,
            exc_info=True,
        )

    return None


def _build_testimony_link(testimony: Testimony) -> str:
    """
    Build the TownLIT profile-scoped Testimony deep link.
    """
    owner_user = _get_owner_user(testimony)
    username = getattr(owner_user, "username", None) or "user"

    kind = testimony.type

    if kind == Testimony.TYPE_WRITTEN:
        type_param = "read"
        k_param = "testimonies.written"

    elif kind == Testimony.TYPE_VIDEO:
        type_param = "video"
        k_param = "testimonies.video"

    elif kind == Testimony.TYPE_AUDIO:
        type_param = "audio"
        k_param = "testimonies.audio"

    else:
        type_param = "read"
        k_param = "testimonies"

    entry_path = "/profiles/members/profile"
    e_param = quote(entry_path, safe="")
    title = testimony.title or ""
    t_param = quote(title, safe="")

    base_path = f"/lit/{username}/content/{username}"

    query_parts = [
        f"type={type_param}",
        f"e={e_param}",
        f"t={t_param}",
        "s=profile",
        f"k={k_param}",
        "o=user",
    ]

    if kind in (
        Testimony.TYPE_VIDEO,
        Testimony.TYPE_AUDIO,
    ):
        query_parts.append("a=auto")
        query_parts.append("p=0")

    return f"{base_path}?{'&'.join(query_parts)}"


def _classify_testimony_kind(instance: Testimony) -> str:
    """Map Testimony.type to its notification presentation kind."""
    if instance.type == Testimony.TYPE_AUDIO:
        return "audio"

    if instance.type == Testimony.TYPE_VIDEO:
        return "video"

    return "written"


def _pick_notif_type_for_kind(kind: str) -> str:
    """Map Testimony kind to the stable notification type."""
    if kind == "audio":
        return "new_testimony_audio"

    if kind == "video":
        return "new_testimony_video"

    return "new_testimony_written"


def _build_notification_message(
    author: CustomUser,
    kind: str,
) -> str:
    return build_testimony_message(
        author,
        kind,
    )


def notify_testimony_ready(testimony: Testimony):
    """
    Send notifications when a Testimony becomes fully available.
    """
    if not testimony.is_available():
        return

    if (
        not testimony.is_active
        or testimony.is_hidden
        or testimony.is_suspended
    ):
        return

    owner_user = _get_owner_user(testimony)
    if not owner_user:
        return

    recipients_qs = _get_accepted_friends(owner_user)

    if not recipients_qs.exists():
        return

    kind = _classify_testimony_kind(testimony)
    notif_type = _pick_notif_type_for_kind(kind)
    link = _build_testimony_link(testimony)
    message = _build_notification_message(owner_user, kind)

    for recipient in recipients_qs:
        if recipient.id == owner_user.id:
            continue

        create_and_dispatch_notification(
            recipient=recipient,
            actor=owner_user,
            notif_type=notif_type,
            message=message,
            target_obj=testimony,
            action_obj=None,
            link=link,
            extra_payload={
                "testimony_id": testimony.id,
                "kind": kind,
            },
        )
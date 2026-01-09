# apps/notifications/signals/testimony_signals.py

import logging
from urllib.parse import quote

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q
from django.contrib.auth import get_user_model

from apps.accounts.models import CustomUser
from apps.profiles.models import Friendship
from apps.profiles.constants import ACCEPTED
from apps.posts.models.testimony import Testimony
from apps.notifications.services.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------
# Helper: get accepted friends of a user
# ---------------------------------------------------------
def _get_accepted_friends(user: CustomUser):
    """
    Return queryset of users who are in 'accepted' friendship with this user.
    We use Friendship.status == ACCEPTED and is_active=True.
    """

    friendships = (
        Friendship.objects
        .filter(status=ACCEPTED, is_active=True)
        .filter(Q(from_user=user) | Q(to_user=user))
    )

    friend_ids = []
    for f in friendships:
        if f.from_user_id == user.id:
            friend_ids.append(f.to_user_id)
        else:
            friend_ids.append(f.from_user_id)

    qs = User.objects.filter(id__in=friend_ids, is_active=True)

    logger.debug(
        "[Notif][Testimony] Accepted friends for user %s → %s",
        user.id,
        list(qs.values_list("id", flat=True)),
    )
    return qs


# ---------------------------------------------------------
# Helper: resolve owner user from Testimony.content_object
# ---------------------------------------------------------
def _get_owner_user(instance: Testimony) -> CustomUser | None:
    """
    Resolve the underlying CustomUser who owns this testimony.

    - If content_object is a Member → use member.user
    - If content_object has .user which is CustomUser → use that
    - If content_object itself is CustomUser → use directly
    """

    obj = instance.content_object
    if not obj:
        return None

    try:
        # Local import to avoid potential circular imports
        from apps.profiles.models import Member

        # Member → member.user
        if isinstance(obj, Member) and isinstance(obj.user, CustomUser):
            return obj.user

        # Generic “has user field”
        if hasattr(obj, "user") and isinstance(obj.user, CustomUser):
            return obj.user

        # Direct user (safety fallback)
        if isinstance(obj, CustomUser):
            return obj

    except Exception as e:
        logger.warning(
            "[Notif][Testimony] Failed to resolve owner user for testimony %s: %s",
            getattr(instance, "id", None),
            e,
            exc_info=True,
        )
        return None

    return None


# ---------------------------------------------------------
# Helper: build frontend deep-link for Testimony
# ---------------------------------------------------------
def _build_testimony_link(testimony: Testimony) -> str:
    """
    Build TownLIT frontend deep-link for this testimony.

    Examples we want:

    Written:
      /lit/{username}/content/{username}?type=read
        &e=%2Fprofiles%2Fmembers%2Fprofile
        &t=...
        &s=profile
        &k=testimonies.written
        &o=user

    Video:
      /lit/{username}/content/{username}?type=video
        &e=%2Fprofiles%2Fmembers%2Fprofile
        &t=Video+testimony+by+Gabby_sakkaki
        &a=auto
        &p=0
        &s=profile
        &k=testimonies.video
        &o=user

    Audio:
      Similar to video, with type=audio and k=testimonies.audio
    """

    # 1) Resolve owner username (Member → user.username)
    owner_user = _get_owner_user(testimony)
    username = getattr(owner_user, "username", None) or "user"

    # 2) Determine kind-specific params
    kind = testimony.type  # "audio" | "video" | "written"

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
        # Safe fallback
        type_param = "read"
        k_param = "testimonies"

    # 3) Encode query parameters
    # e → encoded entry path
    entry_path = "/profiles/members/profile"
    e_param = quote(entry_path, safe="")  # -> %2Fprofiles%2Fmembers%2Fprofile

    # t → title (can contain spaces / Persian characters)
    title = testimony.title or ""
    t_param = quote(title, safe="")

    # 4) Base path
    base_path = f"/lit/{username}/content/{username}"

    # Base query (common)
    query_parts = [
        f"type={type_param}",
        f"e={e_param}",
        f"t={t_param}",
        "s=profile",
        f"k={k_param}",
        "o=user",
    ]

    # For video/audio add autoplay/page params
    if kind in (Testimony.TYPE_VIDEO, Testimony.TYPE_AUDIO):
        query_parts.append("a=auto")
        query_parts.append("p=0")

    query_string = "&".join(query_parts)

    return f"{base_path}?{query_string}"


# ---------------------------------------------------------
# Helper: map type → kind / notif_type
# ---------------------------------------------------------
def _classify_testimony_kind(instance: Testimony) -> str:
    """
    Map Testimony.type to 'written' / 'audio' / 'video'.
    """
    if instance.type == Testimony.TYPE_AUDIO:
        return "audio"
    if instance.type == Testimony.TYPE_VIDEO:
        return "video"
    return "written"


def _pick_notif_type_for_kind(kind: str) -> str:
    """
    Return notification_type key for this testimony kind.
    Must match NOTIFICATION_TYPES in notifications/constants.py.
    """
    if kind == "audio":
        return "new_testimony_audio"
    if kind == "video":
        return "new_testimony_video"
    return "new_testimony_written"


def _build_notification_message(author: CustomUser, kind: str) -> str:
    """
    Brand-aligned, warm notification message for shared testimonies.
    """
    username = getattr(author, "username", "Someone")

    if kind == "audio":
        return (
            f"{username} has shared an audio testimony — "
            f"a living voice of faith, hope, and reflection 🤍"
        )

    if kind == "video":
        return (
            f"{username} has shared a video testimony — "
            f"a moment of truth and light worth witnessing 🤍"
        )

    if kind == "written":
        return (
            f"{username} has shared a written testimony — "
            f"words shaped by journey, grace, and faith 🤍"
        )

    # Fallback – safe and brand-consistent
    return (
        f"{username} has shared a testimony — "
        f"a glimpse of light from a living journey 🤍"
    )


# ---------------------------------------------------------
# Signal: on new testimony created
# ---------------------------------------------------------
@receiver(post_save, sender=Testimony, dispatch_uid="notif.testimony_new_v2")
def on_testimony_created(sender, instance: Testimony, created, **kwargs):
    """
    When a new testimony is created and active, notify all accepted friends
    of the owner user via:
      - DB Notification
      - WebSocket (Notification center)
      - Push (FCM)
      - Email
    """

    if not created:
        return

    # Only notify for active & visible testimonies
    if not instance.is_active or instance.is_hidden or instance.is_suspended:
        logger.debug(
            "[Notif][Testimony] Testimony %s is not public (active/hidden/suspended) → skip.",
            instance.id,
        )
        return

    # Resolve owner CustomUser
    owner_user = _get_owner_user(instance)
    if not owner_user:
        logger.debug(
            "[Notif][Testimony] Could not resolve owner user for testimony %s → skip.",
            instance.id,
        )
        return

    # Friends to notify
    recipients_qs = _get_accepted_friends(owner_user)
    if not recipients_qs.exists():
        logger.debug(
            "[Notif][Testimony] No accepted friends to notify for testimony %s.",
            instance.id,
        )
        return

    kind = _classify_testimony_kind(instance)
    notif_type = _pick_notif_type_for_kind(kind)
    link = _build_testimony_link(instance)

    for recipient in recipients_qs:
        # Safety guard (should never be true, but just in case)
        if recipient.id == owner_user.id:
            continue

        msg_text = _build_notification_message(owner_user, kind)

        create_and_dispatch_notification(
            recipient=recipient,
            actor=owner_user,
            notif_type=notif_type,
            message=msg_text,
            target_obj=instance,
            action_obj=None,
            link=link,
            extra_payload={
                "testimony_id": instance.id,
                "kind": kind,
            },
        )

        logger.debug(
            "[Notif][Testimony] %s (%s) → %s (testimony=%s, link=%s)",
            notif_type,
            kind,
            recipient.username,
            instance.id,
            link,
        )

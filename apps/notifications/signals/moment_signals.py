# apps/notifications/signals/moment_signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q
from django.contrib.auth import get_user_model
from urllib.parse import quote

from apps.posts.models.moment import Moment
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
# Helper: get owner CustomUser from Moment.content_object
# ---------------------------------------------------------
def _get_owner_user(moment: Moment):
    obj = moment.content_object
    if not obj:
        return None

    try:
        if isinstance(obj, Member):
            return obj.user

        if hasattr(obj, "user"):
            return obj.user

        if isinstance(obj, User):
            return obj

    except Exception as e:
        logger.warning(
            "[Notif][Moment] Failed to resolve owner user for moment %s: %s",
            moment.id,
            e,
            exc_info=True,
        )

    return None


# ---------------------------------------------------------
# Helper: get accepted friends
# ---------------------------------------------------------
def _get_accepted_friends(user):
    friendships = (
        Friendship.objects
        .filter(status=ACCEPTED, is_active=True)
        .filter(Q(from_user=user) | Q(to_user=user))
    )

    friend_ids = []
    for f in friendships:
        friend_ids.append(
            f.to_user_id if f.from_user_id == user.id else f.from_user_id
        )

    return User.objects.filter(id__in=friend_ids, is_active=True)


# ---------------------------------------------------------
# Helper: determine moment kind
# ---------------------------------------------------------
def _classify_moment_kind(moment: Moment) -> str:
    if moment.video:
        return "video"
    return "image"


def _pick_notif_type(kind: str) -> str:
    return (
        "new_moment_video"
        if kind == "video"
        else "new_moment_image"
    )


def _build_message(author, kind: str) -> str:
    username = getattr(author, "username", "Someone")
    if kind == "video":
        return f"{username} shared a new video moment"
    return f"{username} shared a new image moment"


# ---------------------------------------------------------
# Helper: build frontend deep-link for Moment (visitor-safe)
# ---------------------------------------------------------
def _build_moment_link(moment: Moment) -> str:
    """
    ✅ Always generate PROFILE-scope link (visitor-safe).
    This works for both authenticated + anonymous, thanks to profileMediaSmart.ts.

    Example:
      /lit/{username}/content/{username}?type=media
        &e=%2Fprofiles%2Fmembers%2Fprofile
        &s=profile
        &k=moments.video|moments.image
        &o=user
        &focus=moment:moment-202601...
        &a=auto
        &p=1
    """

    owner_user = _get_owner_user(moment)
    username = getattr(owner_user, "username", None) or "user"

    # Kind-specific keyPath (used by profile viewer + smart resolver)
    if moment.video:
        k_param = "moments.video"
    else:
        k_param = "moments.image"

    # Entry path must match VisitorProfileViewSet.profile action
    entry_path = "/profiles/members/profile"
    e_param = quote(entry_path, safe="")

    # Base path (profile scope uses username as the page slug)
    u = quote(username, safe="")
    base_path = f"/lit/{u}/content/{u}"

    # Focus token must match your profileMediaSmart parser
    focus_param = quote(f"moment:{moment.slug}", safe="")

    query_parts = [
        "type=media",
        f"e={e_param}",
        "s=profile",
        f"k={k_param}",
        "o=user",
        f"focus={focus_param}",
        "a=auto",  # aspect hint
        "p=1",     # usePoster=true
    ]

    return f"{base_path}?{'&'.join(query_parts)}"



# ---------------------------------------------------------
# Signal: on new moment
# ---------------------------------------------------------
@receiver(post_save, sender=Moment, dispatch_uid="notif.moment.created.v1")
def on_moment_created(sender, instance: Moment, created, **kwargs):

    if not created:
        return

    # Visibility & moderation guards
    if (
        not instance.is_active
        or instance.is_hidden
        or instance.is_suspended
    ):
        logger.debug(
            "[Notif][Moment] Moment %s is not visible → skip",
            instance.id,
        )
        return

    # PRIVATE moments never notify
    if instance.visibility == VISIBILITY_PRIVATE:
        return

    owner_user = _get_owner_user(instance)
    if not owner_user:
        return

    # Determine recipients
    recipients_qs = User.objects.none()

    if instance.visibility in (VISIBILITY_FRIENDS, VISIBILITY_COVENANT):
        recipients_qs = _get_accepted_friends(owner_user)

    else:
        # GLOBAL / DEFAULT → friends only (safe default)
        recipients_qs = _get_accepted_friends(owner_user)

    if not recipients_qs.exists():
        return

    kind = _classify_moment_kind(instance)
    notif_type = _pick_notif_type(kind)
    link = _build_moment_link(instance)
    message = _build_message(owner_user, kind)

    for recipient in recipients_qs:
        if recipient.id == owner_user.id:
            continue

        create_and_dispatch_notification(
            recipient=recipient,
            actor=owner_user,
            notif_type=notif_type,
            message=message,
            target_obj=instance,
            action_obj=None,
            link=link,
            extra_payload={
                "moment_id": instance.id,
                "kind": kind,
            },
        )

        logger.debug(
            "[Notif][Moment] %s → %s (moment=%s)",
            notif_type,
            recipient.username,
            instance.id,
        )

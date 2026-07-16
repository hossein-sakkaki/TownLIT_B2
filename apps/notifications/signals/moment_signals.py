# apps/notifications/signals/moment_signals.py

import logging
from django.db.models import Q
from django.contrib.auth import get_user_model
from urllib.parse import quote
from django.db import transaction
from django.utils import timezone

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
        return (
            f"{username} shared a moment — "
            f"a glimpse of life, meaning, and presence in motion ✨"
        )

    return (
        f"{username} shared a moment — "
        f"a quiet glimpse of life worth pausing for ✨"
    )


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
def notify_moment_ready(moment: Moment):
    """
    Notify accepted friends exactly once when a Moment first becomes available.

    The persistent dispatch marker is stored on Moment itself, so deleting
    Notification history cannot recreate the original publication event.
    """
    if not moment or not moment.pk:
        return

    owner_user = None
    claimed_moment = None

    with transaction.atomic():
        locked_moment = (
            Moment.objects
            .select_for_update()
            .filter(pk=moment.pk)
            .first()
        )

        if not locked_moment:
            return

        if (
            locked_moment.notification_dispatched_at
            is not None
        ):
            logger.info(
                "[Notif][Moment] Publication already dispatched "
                "moment=%s dispatched_at=%s",
                locked_moment.pk,
                locked_moment.notification_dispatched_at,
            )
            return

        if not locked_moment.is_available():
            logger.info(
                "[Notif][Moment] Moment is not available; skipped "
                "moment=%s",
                locked_moment.pk,
            )
            return

        if (
            not locked_moment.is_active
            or locked_moment.is_hidden
            or locked_moment.is_suspended
        ):
            logger.info(
                "[Notif][Moment] Moment unavailable by moderation; "
                "skipped moment=%s",
                locked_moment.pk,
            )
            return

        if (
            locked_moment.visibility
            == VISIBILITY_PRIVATE
        ):
            logger.info(
                "[Notif][Moment] Private Moment; skipped moment=%s",
                locked_moment.pk,
            )
            return

        owner_user = _get_owner_user(
            locked_moment
        )

        if not owner_user:
            logger.warning(
                "[Notif][Moment] Owner could not be resolved "
                "moment=%s",
                locked_moment.pk,
            )
            return

        claimed_at = timezone.now()

        claimed = (
            Moment.objects
            .filter(
                pk=locked_moment.pk,
                notification_dispatched_at__isnull=True,
            )
            .update(
                notification_dispatched_at=claimed_at,
            )
        )

        if claimed != 1:
            logger.info(
                "[Notif][Moment] Publication claim lost "
                "moment=%s",
                locked_moment.pk,
            )
            return

        locked_moment.notification_dispatched_at = (
            claimed_at
        )
        claimed_moment = locked_moment

    recipients_qs = (
        _get_accepted_friends(owner_user)
        .exclude(pk=owner_user.pk)
    )

    kind = _classify_moment_kind(
        claimed_moment
    )
    notif_type = _pick_notif_type(
        kind
    )
    link = _build_moment_link(
        claimed_moment
    )
    message = _build_message(
        owner_user,
        kind,
    )

    dispatched_count = 0
    failed_count = 0

    for recipient in recipients_qs.iterator(
        chunk_size=200
    ):
        try:
            notification = (
                create_and_dispatch_notification(
                    recipient=recipient,
                    actor=owner_user,
                    notif_type=notif_type,
                    message=message,
                    target_obj=claimed_moment,
                    action_obj=None,
                    link=link,
                    extra_payload={
                        "moment_id": claimed_moment.id,
                        "kind": kind,
                        "publication_event": (
                            "moment_available"
                        ),
                    },
                )
            )

            if notification is not None:
                dispatched_count += 1

        except Exception:
            failed_count += 1

            logger.exception(
                "[Notif][Moment] Recipient dispatch failed "
                "moment=%s recipient=%s",
                claimed_moment.pk,
                getattr(recipient, "pk", None),
            )

    logger.info(
        "[Notif][Moment] Publication dispatch completed "
        "moment=%s recipients=%s dispatched=%s failed=%s",
        claimed_moment.pk,
        recipients_qs.count(),
        dispatched_count,
        failed_count,
    )


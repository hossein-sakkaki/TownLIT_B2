# apps/notifications/signals/moment_signals.py

import logging
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.visibility.constants import VISIBILITY_PRIVATE
from apps.notifications.services.presentation import build_moment_message
from apps.notifications.services.services import create_and_dispatch_notification
from apps.posts.models.moment import Moment
from apps.profiles.constants import ACCEPTED
from apps.profiles.models import Friendship, Member

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_owner_user(moment: Moment):
    """Resolve the CustomUser that owns a Moment."""
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

    except Exception as error:
        logger.warning(
            "[Notif][Moment] Failed to resolve owner user for moment %s: %s",
            moment.id,
            error,
            exc_info=True,
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


def _classify_moment_kind(moment: Moment) -> str:
    return "video" if moment.video else "image"


def _pick_notif_type(kind: str) -> str:
    return "new_moment_video" if kind == "video" else "new_moment_image"


def _build_moment_link(moment: Moment) -> str:
    """
    Build a visitor-safe profile-scoped Moment deep link.

    Example:
      /lit/{username}/content/{username}?type=media
        &e=%2Fprofiles%2Fmembers%2Fprofile
        &s=profile
        &k=moments.video|moments.image
        &o=user
        &focus=moment:...
        &a=auto
        &p=1
    """
    owner_user = _get_owner_user(moment)
    username = getattr(owner_user, "username", None) or "user"

    k_param = "moments.video" if moment.video else "moments.image"

    entry_path = "/profiles/members/profile"
    e_param = quote(entry_path, safe="")
    u = quote(username, safe="")
    focus_param = quote(f"moment:{moment.slug}", safe="")

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

        if locked_moment.notification_dispatched_at is not None:
            logger.info(
                "[Notif][Moment] Publication already dispatched "
                "moment=%s dispatched_at=%s",
                locked_moment.pk,
                locked_moment.notification_dispatched_at,
            )
            return

        if not locked_moment.is_available():
            logger.info(
                "[Notif][Moment] Moment is not available; skipped moment=%s",
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

        if locked_moment.visibility == VISIBILITY_PRIVATE:
            logger.info(
                "[Notif][Moment] Private Moment; skipped moment=%s",
                locked_moment.pk,
            )
            return

        owner_user = _get_owner_user(locked_moment)

        if not owner_user:
            logger.warning(
                "[Notif][Moment] Owner could not be resolved moment=%s",
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
            .update(notification_dispatched_at=claimed_at)
        )

        if claimed != 1:
            logger.info(
                "[Notif][Moment] Publication claim lost moment=%s",
                locked_moment.pk,
            )
            return

        locked_moment.notification_dispatched_at = claimed_at
        claimed_moment = locked_moment

    recipients_qs = (
        _get_accepted_friends(owner_user)
        .exclude(pk=owner_user.pk)
    )

    kind = _classify_moment_kind(claimed_moment)
    notif_type = _pick_notif_type(kind)
    link = _build_moment_link(claimed_moment)
    message = build_moment_message(owner_user, kind)

    dispatched_count = 0
    failed_count = 0

    for recipient in recipients_qs.iterator(chunk_size=200):
        try:
            notification = create_and_dispatch_notification(
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
                    "publication_event": "moment_available",
                },
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
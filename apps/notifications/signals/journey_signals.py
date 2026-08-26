# apps/notifications/signals/journey_signals.py

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.core.visibility.constants import (
    VISIBILITY_PRIVATE,
)
from apps.core.visibility.policy import (
    VisibilityPolicy,
)
from apps.notifications.services.audience import (
    accepted_friend_users,
)
from apps.notifications.services.services import (
    create_and_dispatch_notification,
)
from apps.posts.models.journey import (
    JourneyEntry,
)
from apps.posts.services.journeys.links import (
    build_journey_entry_link,
)


logger = logging.getLogger(
    __name__
)


def _build_journey_message(
    owner_user,
) -> str:
    username = (
        getattr(
            owner_user,
            "username",
            None,
        )
        or "Someone"
    )

    return (
        f"{username} added something new "
        f"to their Journey ✨"
    )


def notify_journey_entry_ready(
    entry: JourneyEntry,
):
    """
    Process one newly available JourneyEntry.

    Publication policy:
    - each JourneyEntry event is claimed exactly once;
    - private/unavailable entries do not generate friend notifications;
    - visibility is checked per recipient;
    - Boundary/Stillness remain owned by the central notification service;
    - publication notifications are coalesced per daily Journey because
      target_obj is the parent Journey and action_obj is None.

    Therefore:
    - Entry #1 normally creates + delivers the notification;
    - Entry #2...#12 update the same notification row/link;
    - no 12-push storm is created.
    """

    if not entry or not entry.pk:
        return

    owner_user = None
    claimed_entry = None

    with transaction.atomic():
        locked_entry = (
            JourneyEntry.objects
            .select_for_update()
            .select_related(
                "journey",
                "content_type",
            )
            .filter(
                pk=entry.pk
            )
            .first()
        )

        if locked_entry is None:
            return

        if (
            locked_entry
            .notification_dispatched_at
            is not None
        ):
            logger.info(
                "[Notif][Journey] Entry already processed "
                "entry=%s dispatched_at=%s",
                locked_entry.pk,
                locked_entry.notification_dispatched_at,
            )
            return

        if not locked_entry.is_live:
            logger.info(
                "[Notif][Journey] Entry is not live; "
                "skipped entry=%s",
                locked_entry.pk,
            )
            return

        if (
            locked_entry.visibility
            == VISIBILITY_PRIVATE
        ):
            logger.info(
                "[Notif][Journey] Private entry; "
                "skipped entry=%s",
                locked_entry.pk,
            )
            return

        owner_user = (
            locked_entry.owner_user
        )

        if owner_user is None:
            logger.warning(
                "[Notif][Journey] Owner could not "
                "be resolved entry=%s",
                locked_entry.pk,
            )
            return

        claimed_at = timezone.now()

        claimed = (
            JourneyEntry.objects
            .filter(
                pk=locked_entry.pk,
                notification_dispatched_at__isnull=True,
            )
            .update(
                notification_dispatched_at=claimed_at,
            )
        )

        if claimed != 1:
            logger.info(
                "[Notif][Journey] Publication claim lost "
                "entry=%s",
                locked_entry.pk,
            )
            return

        locked_entry.notification_dispatched_at = (
            claimed_at
        )

        claimed_entry = (
            locked_entry
        )

    recipients = (
        accepted_friend_users(
            owner_user
        )
    )

    link = build_journey_entry_link(
        entry_slug=claimed_entry.slug,
        entry_id=claimed_entry.pk,
        journey_id=claimed_entry.journey_id,
    )

    message = _build_journey_message(
        owner_user
    )

    processed_count = 0
    failed_count = 0
    visibility_skipped_count = 0

    for recipient in recipients.iterator(
        chunk_size=200
    ):
        try:
            # Entry-level visibility remains authoritative.
            if not VisibilityPolicy.can_view(
                viewer=recipient,
                obj=claimed_entry,
            ):
                visibility_skipped_count += 1
                continue

            create_and_dispatch_notification(
                recipient=recipient,
                actor=owner_user,
                notif_type="new_journey",
                message=message,

                # IMPORTANT:
                # Parent Journey is the dedupe target.
                # Therefore all 12 Entries for the same
                # local-day Journey collapse into one row.
                target_obj=claimed_entry.journey,

                # Keep this None so Entry ID does not
                # fragment the dedupe key.
                action_obj=None,

                # But navigation always points at the exact
                # newly published Entry.
                link=link,

                dedupe=True,

                extra_payload={
                    "publication_event":
                        "journey_entry_available",

                    "journey_id":
                        claimed_entry.journey_id,

                    "journey_entry_id":
                        claimed_entry.pk,

                    "journey_entry_slug":
                        claimed_entry.slug,

                    "journey_sequence":
                        claimed_entry.sequence,
                },
            )

            processed_count += 1

        except Exception:
            failed_count += 1

            logger.exception(
                "[Notif][Journey] Recipient dispatch "
                "failed entry=%s recipient=%s",
                claimed_entry.pk,
                getattr(
                    recipient,
                    "pk",
                    None,
                ),
            )

    logger.info(
        "[Notif][Journey] Publication processed "
        "entry=%s journey=%s "
        "processed=%s visibility_skipped=%s failed=%s",
        claimed_entry.pk,
        claimed_entry.journey_id,
        processed_count,
        visibility_skipped_count,
        failed_count,
    )
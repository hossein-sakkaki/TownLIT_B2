# apps/posts/services/journeys/views.py
#
# TownLIT
#
# Created by Hossein Sakkaki.
# Last Update by Hossein Sakkaki on 2026-08-10.
#

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.posts.constants.journeys import JourneyViewSource
from apps.posts.models.journey import JourneyEntry, JourneyEntryView


@dataclass(frozen=True)
class JourneyViewRecordResult:
    record: JourneyEntryView | None
    created: bool
    ignored_owner_view: bool


@transaction.atomic
def record_journey_entry_view(
    *,
    entry: JourneyEntry,
    viewer,
    progress_ms: int = 0,
    completed: bool = False,
    source: str = JourneyViewSource.OTHER,
) -> JourneyViewRecordResult:
    """
    Record an authenticated non-owner Journey view.

    Public view count represents unique viewers.
    Per-viewer view_count represents separate visit starts.
    Completion/progress updates never create another visit.
    """

    # Serialize writes for the same Entry.
    locked_entry = (
        JourneyEntry.objects
        .select_for_update()
        .get(pk=entry.pk)
    )

    owner_user = locked_entry.owner_user

    if owner_user and owner_user.pk == viewer.pk:
        return JourneyViewRecordResult(
            record=None,
            created=False,
            ignored_owner_view=True,
        )

    now = timezone.now()

    safe_progress = max(
        0,
        min(
            int(progress_ms or 0),
            int(locked_entry.display_duration_ms),
        ),
    )

    # The client sends progress=0/completed=False when a viewing
    # session starts. Completion is a separate update request.
    is_visit_start = (
        safe_progress == 0
        and not bool(completed)
    )

    record = (
        JourneyEntryView.objects
        .select_for_update()
        .filter(
            entry=locked_entry,
            viewer=viewer,
        )
        .first()
    )

    created = record is None

    if created:
        record = JourneyEntryView.objects.create(
            entry=locked_entry,
            viewer=viewer,
            first_viewed_at=now,
            last_viewed_at=now,
            view_count=1,
            max_progress_ms=safe_progress,
            completed=bool(completed),
            source=source,
        )

    else:
        update_fields = [
            "last_viewed_at",
            "source",
            "updated_at",
        ]

        record.last_viewed_at = now
        record.source = source

        # Count only a new visit start, never the completion
        # request belonging to that same visit.
        if is_visit_start:
            record.view_count = F("view_count") + 1
            update_fields.append("view_count")

        if safe_progress > record.max_progress_ms:
            record.max_progress_ms = safe_progress
            update_fields.append("max_progress_ms")

        if completed and not record.completed:
            record.completed = True
            update_fields.append("completed")

        record.save(
            update_fields=update_fields
        )

        # Resolve any F() expression back to concrete values.
        record.refresh_from_db()

    entry_updates = {
        "last_viewed_at": now,
    }

    # Public Journey views are unique viewers.
    # Existing viewers never increase this counter again.
    if created:
        entry_updates.update(
            {
                "view_count_internal": (
                    F("view_count_internal") + 1
                ),
                "unique_viewers_count": (
                    F("unique_viewers_count") + 1
                ),
            }
        )

    JourneyEntry.objects.filter(
        pk=locked_entry.pk
    ).update(
        **entry_updates
    )

    return JourneyViewRecordResult(
        record=record,
        created=created,
        ignored_owner_view=False,
    )
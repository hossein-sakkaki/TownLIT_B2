# apps/posts/services/journeys/views.py

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
    Record authenticated non-owner Journey view.
    """

    owner_user = entry.owner_user

    if owner_user and owner_user.pk == viewer.pk:
        return JourneyViewRecordResult(
            record=None,
            created=False,
            ignored_owner_view=True,
        )

    now = timezone.now()

    record = (
        JourneyEntryView.objects.select_for_update()
        .filter(
            entry=entry,
            viewer=viewer,
        )
        .first()
    )

    created = record is None

    safe_progress = max(
        0,
        min(
            int(progress_ms or 0),
            int(entry.display_duration_ms),
        ),
    )

    if record is None:
        record = JourneyEntryView.objects.create(
            entry=entry,
            viewer=viewer,
            first_viewed_at=now,
            last_viewed_at=now,
            view_count=1,
            max_progress_ms=safe_progress,
            completed=bool(completed),
            source=source,
        )
    else:
        record.last_viewed_at = now
        record.view_count = F("view_count") + 1

        if safe_progress > record.max_progress_ms:
            record.max_progress_ms = safe_progress

        if completed:
            record.completed = True

        record.source = source

        record.save(
            update_fields=[
                "last_viewed_at",
                "view_count",
                "max_progress_ms",
                "completed",
                "source",
                "updated_at",
            ]
        )

        record.refresh_from_db()

    update_values = {
        "view_count_internal": F("view_count_internal") + 1,
        "last_viewed_at": now,
    }

    if created:
        update_values["unique_viewers_count"] = (
            F("unique_viewers_count") + 1
        )

    JourneyEntry.objects.filter(pk=entry.pk).update(**update_values)

    return JourneyViewRecordResult(
        record=record,
        created=created,
        ignored_owner_view=False,
    )
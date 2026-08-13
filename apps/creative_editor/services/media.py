# apps/creative_editor/services/media.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-10.
# Last Update by Hossein Sakkaki on 2026-08-10.
#

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.creative_editor.models import (
    CreativeCompositionMedia,
    CreativeRenderJob,
)
from apps.creative_editor.services.document import (
    extract_document_references,
)


@transaction.atomic
def archive_composition_media(
    *,
    media: CreativeCompositionMedia,
) -> CreativeCompositionMedia:
    """
    Archive unreferenced composition media.
    """

    locked = (
        CreativeCompositionMedia.objects
        .select_for_update()
        .select_related(
            "composition"
        )
        .get(pk=media.pk)
    )

    if not locked.is_active:
        return locked

    composition = locked.composition
    public_id = str(
        locked.public_id
    )

    current_references = (
        extract_document_references(
            composition.document or {}
        )
    )

    if public_id in current_references.media_public_ids:
        raise ValidationError(
            {
                "media": (
                    "This media is referenced by the "
                    "current composition document."
                ),
            }
        )

    active_jobs = (
        CreativeRenderJob.objects
        .filter(
            composition=composition,
            status__in=[
                CreativeRenderJob.Status.QUEUED,
                CreativeRenderJob.Status.PROCESSING,
            ],
        )
        .only(
            "id",
            "document_snapshot",
        )
    )

    for job in active_jobs:
        references = extract_document_references(
            job.document_snapshot or {}
        )

        if public_id in references.media_public_ids:
            raise ValidationError(
                {
                    "media": (
                        "This media is referenced by an "
                        "active render job."
                    ),
                }
            )

    locked.is_active = False

    locked.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    return locked
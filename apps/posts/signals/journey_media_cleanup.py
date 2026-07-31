# apps/posts/signals/journey_media_cleanup.py

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from apps.posts.models.journey import JourneyEntry
from apps.posts.services.journeys.audio_usage import revoke_journey_audio_usage
from apps.posts.services.journeys.storage import delete_storage_asset


logger = logging.getLogger(__name__)


@receiver(
    pre_delete,
    sender=JourneyEntry,
    dispatch_uid="journey.cleanup.audio.revoke.v1",
)
def journey_entry_revoke_audio_before_delete(
    sender,
    instance: JourneyEntry,
    **kwargs,
):
    """
    Revoke active music grants before deleting the entry.
    """

    try:
        revoke_journey_audio_usage(
            entry=instance,
            reason="Journey entry was deleted.",
        )
    except Exception:
        logger.exception(
            "Failed revoking Journey audio grants: entry=%s",
            instance.pk,
        )

        # Do not delete content while an active grant may remain.
        raise


@receiver(
    post_delete,
    sender=JourneyEntry,
    dispatch_uid="journey.cleanup.media.delete.v2",
)
def journey_entry_cleanup_media(
    sender,
    instance: JourneyEntry,
    **kwargs,
):
    """
    Delete immutable Journey media after DB commit.
    """

    rendered_key = getattr(instance.rendered_image, "name", "")
    thumbnail_key = getattr(instance.thumbnail, "name", "")

    def cleanup():
        delete_storage_asset(rendered_key)
        delete_storage_asset(thumbnail_key)

    transaction.on_commit(cleanup)
    
    
    
    




# docker compose exec -T backend python manage.py shell <<'PY'
# from django.apps import apps
# from django.db import transaction
# from django.db.models import Q

# from apps.creative_editor.models import (
#     CreativeComposition,
#     CreativeRenderJob,
# )
# from apps.posts.models.journey import (
#     Journey,
#     JourneyEntry,
#     JourneyEntryView,
# )


# def optional_model(app_label, model_name):
#     try:
#         return apps.get_model(app_label, model_name)
#     except LookupError:
#         return None


# DailyReflectionPrompt = optional_model(
#     "journey_insights",
#     "DailyReflectionPrompt",
# )

# ReflectionAnswer = optional_model(
#     "journey_insights",
#     "ReflectionAnswer",
# )

# ReflectionSessionQuestion = optional_model(
#     "journey_insights",
#     "ReflectionSessionQuestion",
# )

# ReflectionSession = optional_model(
#     "journey_insights",
#     "ReflectionSession",
# )


# print("\n=== JOURNEY TEST CLEANUP ===")

# with transaction.atomic():
#     journey_entry_ids = list(
#         JourneyEntry.objects.values_list(
#             "pk",
#             flat=True,
#         )
#     )

#     journey_ids = list(
#         Journey.objects.values_list(
#             "pk",
#             flat=True,
#         )
#     )

#     composition_ids_from_entries = set(
#         JourneyEntry.objects.exclude(
#             composition_id__isnull=True
#         ).values_list(
#             "composition_id",
#             flat=True,
#         )
#     )

#     render_job_ids_from_entries = set(
#         JourneyEntry.objects.exclude(
#             render_job_id__isnull=True
#         ).values_list(
#             "render_job_id",
#             flat=True,
#         )
#     )

#     journey_composition_ids = set(
#         CreativeComposition.objects.filter(
#             metadata__consumer="journey"
#         ).values_list(
#             "pk",
#             flat=True,
#         )
#     )

#     composition_ids = (
#         composition_ids_from_entries
#         | journey_composition_ids
#     )

#     journey_render_job_ids = set(
#         CreativeRenderJob.objects.filter(
#             composition_id__in=composition_ids
#         ).values_list(
#             "pk",
#             flat=True,
#         )
#     )

#     render_job_ids = (
#         render_job_ids_from_entries
#         | journey_render_job_ids
#     )

#     view_count = JourneyEntryView.objects.filter(
#         entry_id__in=journey_entry_ids
#     ).count()

#     entry_count = len(journey_entry_ids)
#     journey_count = len(journey_ids)
#     composition_count = len(composition_ids)
#     render_job_count = len(render_job_ids)

#     prompt_count = (
#         DailyReflectionPrompt.objects.count()
#         if DailyReflectionPrompt is not None
#         else 0
#     )

#     answer_count = (
#         ReflectionAnswer.objects.count()
#         if ReflectionAnswer is not None
#         else 0
#     )

#     assignment_count = (
#         ReflectionSessionQuestion.objects.count()
#         if ReflectionSessionQuestion is not None
#         else 0
#     )

#     session_count = (
#         ReflectionSession.objects.count()
#         if ReflectionSession is not None
#         else 0
#     )

#     print("Journey views:", view_count)
#     print("Journey entries:", entry_count)
#     print("Journeys:", journey_count)
#     print("Daily prompts:", prompt_count)
#     print("Reflection answers:", answer_count)
#     print("Reflection assignments:", assignment_count)
#     print("Reflection sessions:", session_count)
#     print("Journey render jobs:", render_job_count)
#     print("Journey compositions:", composition_count)

#     # Remove reflection data created by Journey publishing.
#     if DailyReflectionPrompt is not None:
#         DailyReflectionPrompt.objects.all().delete()

#     if ReflectionAnswer is not None:
#         ReflectionAnswer.objects.all().delete()

#     if ReflectionSessionQuestion is not None:
#         ReflectionSessionQuestion.objects.all().delete()

#     if ReflectionSession is not None:
#         ReflectionSession.objects.all().delete()

#     # Views would cascade, but explicit deletion keeps cleanup visible.
#     if journey_entry_ids:
#         JourneyEntryView.objects.filter(
#             entry_id__in=journey_entry_ids
#         ).delete()

#     # Triggers audio grant revocation and Journey media cleanup signals.
#     if journey_entry_ids:
#         JourneyEntry.objects.filter(
#             pk__in=journey_entry_ids
#         ).delete()

#     if journey_ids:
#         Journey.objects.filter(
#             pk__in=journey_ids
#         ).delete()

#     # Delete render jobs before compositions.
#     if render_job_ids:
#         CreativeRenderJob.objects.filter(
#             pk__in=render_job_ids
#         ).delete()

#     if composition_ids:
#         CreativeComposition.objects.filter(
#             pk__in=composition_ids
#         ).delete()


# print("\n=== REMAINING RECORDS ===")
# print("Journeys:", Journey.objects.count())
# print("Journey entries:", JourneyEntry.objects.count())
# print("Journey views:", JourneyEntryView.objects.count())

# if DailyReflectionPrompt is not None:
#     print(
#         "Daily prompts:",
#         DailyReflectionPrompt.objects.count(),
#     )

# if ReflectionAnswer is not None:
#     print(
#         "Reflection answers:",
#         ReflectionAnswer.objects.count(),
#     )

# if ReflectionSessionQuestion is not None:
#     print(
#         "Reflection assignments:",
#         ReflectionSessionQuestion.objects.count(),
#     )

# if ReflectionSession is not None:
#     print(
#         "Reflection sessions:",
#         ReflectionSession.objects.count(),
#     )

# print(
#     "Journey compositions:",
#     CreativeComposition.objects.filter(
#         Q(metadata__consumer="journey")
#         | Q(pk__in=composition_ids)
#     ).count(),
# )

# print(
#     "Journey render jobs:",
#     CreativeRenderJob.objects.filter(
#         Q(pk__in=render_job_ids)
#         | Q(composition_id__in=composition_ids)
#     ).count(),
# )

# print("\nCleanup completed successfully.")
# PY
# apps/translations/tasks.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki (original creation date not recorded in source).
# Last Update by Hossein Sakkaki on 2026-11-09.

"""Translation cache cleanup and bounded asynchronous generation."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.translations.models import TranslationCache
from apps.translations.services.automatic_dispatch import (
    _dispatch_cache,
    automatic_dispatch_enabled,
    automatic_job_key,
    automatic_text_limit,
    is_automatic_field_supported,
)
from apps.translations.services.base import _normalize_source_text, translate_cached
from apps.translations.services.exceptions import EmptySourceTextError
from apps.translations.services.hashing import hash_text
from apps.translations.services.language import (
    canonical_supported_language,
    resolve_user_primary_language,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def purge_stale_translations(self, days: int = 90) -> dict:
    """Purge translations not accessed within the specified TTL."""
    effective_days = max(int(days), 1)
    cutoff = timezone.now() - timedelta(days=effective_days)
    deleted_count, _ = TranslationCache.objects.filter(
        last_accessed_at__lt=cutoff,
    ).delete()
    return {
        "deleted": deleted_count,
        "cutoff": cutoff.isoformat(),
        "ttl_days": effective_days,
    }


def _automatic_authorized_object(*, obj, viewer):
    """Revalidate current visibility and hold state just before translation."""
    from apps.core.streams.constants import STREAM_SCOPE_GLOBAL
    from apps.core.streams.query import StreamQuery
    from apps.sanctuary.services.held_content_access import held_representation_or_none

    target = getattr(obj, "prayer", None) if obj._meta.model_name == "prayerresponse" else obj
    if target is None:
        return None
    if getattr(target, "is_active", True) is False:
        return None
    if getattr(target, "is_suspended", False) or getattr(target, "is_hidden", False):
        return None

    visible = StreamQuery.seed_queryset(
        model=type(target), viewer=viewer, scope=STREAM_SCOPE_GLOBAL,
    ).filter(pk=target.pk).exists()
    if not visible:
        return None

    if held_representation_or_none(target=target, viewer=viewer, data={}) is None:
        return None
    if target is not obj and held_representation_or_none(
        target=obj, viewer=viewer, data={},
    ) is None:
        return None
    return obj


@shared_task(
    bind=True,
    queue="default",
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 2},
    soft_time_limit=100,
    time_limit=120,
)
def generate_automatic_translation_task(
    self,
    *,
    content_type_id: int,
    object_id: int,
    field_name: str,
    target_language: str,
    source_text_hash: str,
    viewer_id: int,
) -> dict:
    """Generate a cached translation only while source and access remain valid."""
    if not automatic_dispatch_enabled():
        return {"status": "disabled"}

    canonical = canonical_supported_language(target_language)
    if canonical is None or canonical != target_language:
        return {"status": "unsupported_language"}
    if not isinstance(source_text_hash, str) or len(source_text_hash) != 64:
        return {"status": "invalid_hash"}

    content_type = ContentType.objects.get_for_id(content_type_id)
    from apps.posts.models.moment import Moment
    from apps.posts.models.pray import Prayer, PrayerResponse
    from apps.posts.models.testimony import Testimony
    allowed_models = {Moment, Prayer, PrayerResponse, Testimony}
    model = content_type.model_class()
    if model not in allowed_models:
        return {"status": "unsupported_model"}
    obj = model.objects.filter(pk=object_id).first()
    if obj is None or not is_automatic_field_supported(obj, field_name):
        return {"status": "unsupported_field_or_deleted"}

    viewer = get_user_model().objects.filter(pk=viewer_id, is_active=True).first()
    if viewer is None:
        return {"status": "viewer_unavailable"}
    if resolve_user_primary_language(user=viewer) != target_language:
        return {"status": "viewer_language_changed"}

    try:
        allowed = _automatic_authorized_object(obj=obj, viewer=viewer)
    except Exception:
        logger.exception(
            "automatic_translation_visibility_check_failed model=%s id=%s",
            model.__name__, object_id,
        )
        return {"status": "visibility_unavailable"}
    if allowed is None:
        return {"status": "access_restricted"}

    try:
        source = _normalize_source_text(getattr(obj, field_name, None))
    except EmptySourceTextError:
        return {"status": "empty_source"}
    if len(source) > automatic_text_limit():
        return {"status": "over_text_limit"}
    if hash_text(source) != source_text_hash:
        return {"status": "stale_source"}

    cache = _dispatch_cache()
    base_key = automatic_job_key(
        content_type_id=content_type_id,
        object_id=object_id,
        field_name=field_name,
        target_language=target_language,
        source_text_hash=source_text_hash,
    )
    worker_key = f"{base_key}:processing"
    if not cache.add(worker_key, 1, timeout=180):
        return {"status": "already_processing"}

    try:
        # The base service checks the persistent cache again before AWS.
        result = translate_cached(
            obj=obj,
            field_name=field_name,
            user=None,
            target_language=target_language,
            source_language=None,
            humanize=False,
        )
        return {
            "status": "ready",
            "cached": bool(result.get("cached")),
        }
    finally:
        cache.delete(worker_key)

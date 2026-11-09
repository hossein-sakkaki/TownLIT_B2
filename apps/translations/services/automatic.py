# apps/translations/services/automatic.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-07.
# Last Update by Hossein Sakkaki on 2026-11-07.

"""Cache-only automatic translation presentation for authorized content."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.translations.models import TranslationCache
from apps.translations.services.base import (
    _cached_structure_is_valid,
    _normalize_source_text,
)
from apps.translations.services.exceptions import EmptySourceTextError
from apps.translations.services.hashing import hash_text
from apps.translations.services.language import (
    language_codes_match,
    resolve_user_primary_language,
)


def cached_automatic_fields(
    *,
    obj,
    fields: Mapping[str, str | None],
    viewer,
) -> dict:
    """Return original + valid cached translations, without calling providers.

    Authorization MUST already have been checked by the caller's content
    query and serialization gate. This function does not grant visibility.
    """
    if not getattr(viewer, "is_authenticated", False):
        raise ValueError("Automatic translation requires an authenticated viewer.")
    if obj is None or not getattr(obj, "pk", None):
        raise ValueError("Automatic translation requires a persisted content object.")

    target = resolve_user_primary_language(user=viewer)
    sources = {}
    for field_name, value in fields.items():
        if value is None or not str(value).strip():
            continue
        if not field_name or len(field_name) > 50:
            raise ValueError("Invalid automatic translation field name.")
        try:
            source = _normalize_source_text(value)
        except EmptySourceTextError:
            continue
        sources[field_name] = (str(value), source, hash_text(source))

    if not sources:
        return {"target_language": target, "fields": {}}

    content_type = ContentType.objects.get_for_model(
        obj, for_concrete_model=True,
    )
    rows = TranslationCache.objects.filter(
        content_type=content_type,
        object_id=obj.pk,
        target_language=target,
        field_name__in=tuple(sources),
    )
    valid_rows = {}
    for row in rows:
        source = sources.get(row.field_name)
        if source is None or row.source_text_hash != source[2]:
            continue
        if not row.translated_text or not row.translated_text.strip():
            continue
        if not _cached_structure_is_valid(
            source_text=source[1], translated_text=row.translated_text,
        ):
            continue
        valid_rows[row.field_name] = row

    # Automatic reads count as cache access; throttle writes to once per day.
    cutoff = timezone.now() - timedelta(days=1)
    stale_access_ids = [
        row.pk for row in valid_rows.values()
        if row.last_accessed_at < cutoff
    ]
    if stale_access_ids:
        TranslationCache.objects.filter(pk__in=stale_access_ids).update(
            last_accessed_at=timezone.now(),
        )

    result = {}
    for field_name, (original, _source, _hash) in sources.items():
        row = valid_rows.get(field_name)
        if row is None:
            result[field_name] = {
                "original": original,
                "translated": None,
                "source_language": None,
                "status": "missing",
            }
            continue

        source_language = row.source_language or None
        same_language = language_codes_match(source_language, target)
        result[field_name] = {
            "original": original,
            "translated": None if same_language else row.translated_text,
            "source_language": source_language,
            "status": "original" if same_language else "ready",
        }

    return {"target_language": target, "fields": result}

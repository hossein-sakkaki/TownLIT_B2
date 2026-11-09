
# apps/translations/services/automatic_dispatch.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-09.
# Last Update by Hossein Sakkaki on 2026-11-09.

"""Dispatch missing automatic translations without product-imposed quotas."""

from __future__ import annotations

import hashlib
import logging
import math
import os
from collections.abc import Mapping

from django.conf import settings
from django.core.cache import caches

from apps.translations.services.base import _normalize_source_text
from apps.translations.services.exceptions import EmptySourceTextError
from apps.translations.services.hashing import hash_text
from apps.translations.services.language import canonical_supported_language

logger = logging.getLogger(__name__)

AUTOMATIC_STREAM_FIELDS = {
    "posts.moment": frozenset({"caption"}),
    "posts.prayer": frozenset({"caption"}),
    "posts.prayerresponse": frozenset({"response_text"}),
    "posts.testimony": frozenset({"title", "content"}),
}


def _configured(name: str, default):
    return getattr(settings, name, os.getenv(name, default))


def automatic_dispatch_enabled() -> bool:
    value = _configured("TRANSLATIONS_AUTOMATIC_ENABLED", False)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def automatic_stream_request_limit() -> float:
    """Preserve the Stream interface without a per-response quota."""
    return math.inf


def automatic_text_limit() -> float:
    """Preserve the Worker interface without a product text-length cap."""
    return math.inf


def is_automatic_field_supported(obj, field_name: str) -> bool:
    meta = getattr(obj, "_meta", None)
    if meta is None:
        return False

    label = f"{meta.app_label}.{meta.model_name}"

    if field_name not in AUTOMATIC_STREAM_FIELDS.get(label, ()):
        return False

    if label == "posts.testimony" and getattr(obj, "type", None) != "written":
        return False

    return True


def _dispatch_cache():
    alias = str(
        _configured(
            "TRANSLATIONS_AUTOMATIC_CACHE_ALIAS",
            "messenger_throttle",
        )
    )

    backend = caches[alias]

    if "locmem" in backend.__class__.__module__.lower():
        raise RuntimeError(
            "Automatic translation requires a shared cache backend."
        )

    return backend


def automatic_job_key(
    *,
    content_type_id: int,
    object_id: int,
    field_name: str,
    target_language: str,
    source_text_hash: str,
) -> str:
    fingerprint = "|".join(
        (
            str(content_type_id),
            str(object_id),
            field_name,
            target_language,
            source_text_hash,
        )
    )

    digest = hashlib.sha256(
        fingerprint.encode("utf-8")
    ).hexdigest()

    return f"translations:auto:v1:job:{digest}"


def dispatch_missing_automatic_fields(
    *,
    obj,
    presentation: Mapping,
    viewer,
    remaining: int | float,
) -> int:
    """Enqueue eligible cache misses without blocking on the provider.

    The caller authorizes content before dispatch. The Worker rechecks
    current permissions, source hash, and primary language.
    """
    if not automatic_dispatch_enabled() or remaining <= 0:
        return 0

    viewer_id = getattr(viewer, "pk", None)

    if (
        not getattr(viewer, "is_authenticated", False)
        or not viewer_id
    ):
        return 0

    if obj is None or not getattr(obj, "pk", None):
        return 0

    target = canonical_supported_language(
        presentation.get("target_language")
    )

    if not target:
        return 0

    fields = presentation.get("fields")

    if not isinstance(fields, Mapping):
        return 0

    try:
        from django.contrib.contenttypes.models import ContentType
        from apps.translations.tasks import (
            generate_automatic_translation_task,
        )

        cache = _dispatch_cache()

        content_type_id = ContentType.objects.get_for_model(
            obj,
            for_concrete_model=True,
        ).pk

        queued = 0

        for field_name, field in fields.items():
            if queued >= remaining:
                break

            if not is_automatic_field_supported(obj, field_name):
                continue

            if (
                not isinstance(field, Mapping)
                or field.get("status") != "missing"
            ):
                continue

            try:
                source = _normalize_source_text(
                    field.get("original")
                )
            except EmptySourceTextError:
                continue

            source_hash = hash_text(source)

            key = automatic_job_key(
                content_type_id=content_type_id,
                object_id=obj.pk,
                field_name=field_name,
                target_language=target,
                source_text_hash=source_hash,
            )

            if not cache.add(
                key,
                1,
                timeout=10 * 60,
            ):
                continue

            try:
                generate_automatic_translation_task.apply_async(
                    kwargs={
                        "content_type_id": content_type_id,
                        "object_id": obj.pk,
                        "field_name": field_name,
                        "target_language": target,
                        "source_text_hash": source_hash,
                        "viewer_id": viewer_id,
                    },
                    queue="default",
                    retry=False,
                )

                queued += 1

            except Exception:
                cache.delete(key)

                logger.exception(
                    "automatic_translation_dispatch_failed "
                    "model=%s id=%s field=%s",
                    obj._meta.label_lower,
                    obj.pk,
                    field_name,
                )

        return queued

    except Exception:
        logger.exception(
            "automatic_translation_dispatch_unavailable "
            "model=%s id=%s",
            obj.__class__.__name__,
            obj.pk,
        )

        return 0

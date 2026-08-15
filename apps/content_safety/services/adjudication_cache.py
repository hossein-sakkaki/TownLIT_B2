# apps/content_safety/services/adjudication_cache.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.content_safety.models import (
    ContentSafetyAdjudicationCache,
)


def _build_signal_hash(
    *,
    active_categories: list[str],
    local_signals: list[str],
) -> str:
    """
    Hash canonical safety signals.
    """

    payload = {
        "active_categories": sorted(
            {
                str(item).strip()
                for item in active_categories
                if str(item).strip()
            }
        ),
        "local_signals": sorted(
            {
                str(item).strip()
                for item in local_signals
                if str(item).strip()
            }
        ),
    }

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        encoded
    ).hexdigest()


def _expiry():
    return timezone.now() + timedelta(
        days=(
            settings.CONTENT_SAFETY_ADJUDICATION_CACHE_TTL_DAYS
        )
    )


def _resolve_policy_version(
    policy_version: str | None,
) -> str:
    """
    Resolve the cache policy version.

    Text callers may omit it and continue using the existing
    CONTENT_SAFETY_POLICY_VERSION setting.
    """

    resolved = str(
        policy_version
        or settings.CONTENT_SAFETY_POLICY_VERSION
        or ""
    ).strip()

    if not resolved:
        raise RuntimeError(
            "Content safety policy version is missing."
        )

    return resolved


def get_cached_adjudication(
    *,
    input_hash: str,
    context: str,
    active_categories: list[str],
    local_signals: list[str],
    model: str,
    policy_version: str | None = None,
) -> dict | None:
    """
    Return one valid cached adjudication.
    """

    signal_hash = _build_signal_hash(
        active_categories=active_categories,
        local_signals=local_signals,
    )

    resolved_policy_version = _resolve_policy_version(
        policy_version
    )

    cached = (
        ContentSafetyAdjudicationCache.objects
        .filter(
            input_hash=input_hash,
            context=context,
            signal_hash=signal_hash,
            policy_version=resolved_policy_version,
            model=model,
            expires_at__gt=timezone.now(),
        )
        .first()
    )

    if cached is None:
        return None

    cached.touch()

    return {
        "decision": cached.decision,
        "risk_level": cached.risk_level,
        "reason_code": cached.reason_code,
        "model": cached.model,
        "cached": True,
    }


def cache_adjudication(
    *,
    input_hash: str,
    context: str,
    active_categories: list[str],
    local_signals: list[str],
    model: str,
    decision: str,
    risk_level: str,
    reason_code: str,
    policy_version: str | None = None,
) -> None:
    """
    Cache one contextual decision.
    """

    signal_hash = _build_signal_hash(
        active_categories=active_categories,
        local_signals=local_signals,
    )

    resolved_policy_version = _resolve_policy_version(
        policy_version
    )

    defaults = {
        "decision": decision,
        "risk_level": risk_level,
        "reason_code": reason_code,
        "last_accessed_at": timezone.now(),
        "expires_at": _expiry(),
    }

    try:
        with transaction.atomic():
            (
                ContentSafetyAdjudicationCache.objects
                .update_or_create(
                    input_hash=input_hash,
                    context=context,
                    signal_hash=signal_hash,
                    policy_version=resolved_policy_version,
                    model=model,
                    defaults=defaults,
                )
            )

    except IntegrityError:
        # Another request already cached it.
        return
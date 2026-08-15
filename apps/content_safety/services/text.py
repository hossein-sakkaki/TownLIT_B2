# apps/content_safety/services/text.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.content_safety.enums import (
    SafetyContext,
    SafetyDecision,
    SafetyInputType,
    SafetyReason,
    SafetyRiskLevel,
)
from apps.content_safety.exceptions import (
    ContentSafetyBlockedError,
    ContentSafetyReviewError,
    ContentSafetyUnavailableError,
)
from apps.content_safety.models import (
    ContentSafetyAnalysisCache,
    ContentSafetyEvent,
)
from apps.content_safety.services.adjudication import (
    adjudicate_text,
)
from apps.content_safety.services.hashing import (
    hash_safety_input,
)
from apps.content_safety.services.local_signals import (
    inspect_local_text_signals,
)
from apps.content_safety.services.normalization import (
    normalize_text_for_safety,
)
from apps.content_safety.services.policy import (
    active_moderation_categories,
    evaluate_text_policy,
)
from apps.content_safety.services.providers.openai_moderation import (
    OpenAIModerationProvider,
)
from apps.content_safety.services.types import (
    ProviderModerationResult,
    TextSafetyResult,
)
from apps.content_safety.services.adjudication_cache import (
    cache_adjudication,
    get_cached_adjudication,
)

logger = logging.getLogger(
    __name__
)


# -------------------------------------------------------------------------
# Supplemental sexual-language signals
# -------------------------------------------------------------------------
#
# These patterns NEVER block content directly.
#
# Their only purpose is to force contextual adjudication when lightweight
# provider moderation may otherwise consider a short sexualized phrase safe.
#
# This is important for inputs such as:
# - "sexy"
# - "send nudes"
# - "sexting"
#
# At the same time, contextual adjudication can still allow:
# - sexual abuse recovery
# - pastoral discussion
# - educational / clinical discussion
# - prayer for healing
# - personal testimony
#
_SEXUAL_LANGUAGE_PATTERNS = (
    # English
    re.compile(
        r"\bsexy\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsex\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsexual(?:ly|ized|ization)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsext(?:ing|ed|s)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnudes?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnaked\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\berotic(?:a|ally)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bporn(?:o|ography|ographic)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bhorny\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bgenitals?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bpenis\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bvagina\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bboobs?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\btits?\b",
        re.IGNORECASE,
    ),

    # Persian
    re.compile(
        r"سکسی"
    ),
    re.compile(
        r"سکس"
    ),
    re.compile(
        r"رابطه\s*جنسی"
    ),
    re.compile(
        r"محتوا(?:ی)?\s*جنسی"
    ),
    re.compile(
        r"جنسی"
    ),
    re.compile(
        r"پورن"
    ),
    re.compile(
        r"پورنوگراف"
    ),
    re.compile(
        r"برهنه"
    ),
    re.compile(
        r"لخت"
    ),
    re.compile(
        r"واژن"
    ),
    re.compile(
        r"آلت\s*تناسلی"
    ),
    re.compile(
        r"اندام\s*جنسی"
    ),

    # Arabic
    re.compile(
        r"جنسي"
    ),
    re.compile(
        r"إباحي|اباحي|إباحية|اباحية"
    ),
)


def _sexual_language_signals(
    text: str,
) -> tuple[str, ...]:
    """
    Return supplemental sexual-language signal.

    We intentionally store only the signal type, never the matched word.
    """

    if not text:
        return ()

    for pattern in _SEXUAL_LANGUAGE_PATTERNS:
        if pattern.search(
            text
        ):
            return (
                "sexual_language_hint",
            )

    return ()


def _cache_expiry():
    return timezone.now() + timedelta(
        days=settings.CONTENT_SAFETY_CACHE_TTL_DAYS
    )


def _normalize_context(
    value: str,
) -> str:
    context = str(
        value
        or SafetyContext.GENERIC
    ).strip()

    valid_values = {
        choice.value
        for choice in SafetyContext
    }

    if context not in valid_values:
        return SafetyContext.GENERIC

    return context


def _strict_contexts() -> set[str]:
    raw_value = getattr(
        settings,
        "CONTENT_SAFETY_STRICT_CIVILITY_CONTEXTS",
        (),
    )

    if isinstance(
        raw_value,
        str,
    ):
        return {
            item.strip()
            for item in raw_value.split(
                ","
            )
            if item.strip()
        }

    return {
        str(
            item
        ).strip()
        for item in (
            raw_value or ()
        )
        if str(
            item
        ).strip()
    }


def _should_force_adjudication(
    *,
    context: str,
) -> bool:
    if not getattr(
        settings,
        "CONTENT_SAFETY_STRICT_CIVILITY_ENABLED",
        False,
    ):
        return False

    return context in _strict_contexts()


def _get_cached_analysis(
    *,
    input_hash: str,
    provider_name: str,
    provider_model: str,
) -> ProviderModerationResult | None:
    cached = (
        ContentSafetyAnalysisCache.objects
        .filter(
            input_type=SafetyInputType.TEXT,
            input_hash=input_hash,
            provider=provider_name,
            provider_model=provider_model,
            expires_at__gt=timezone.now(),
        )
        .first()
    )

    if cached is None:
        return None

    cached.touch()

    return ProviderModerationResult(
        flagged=cached.flagged,
        categories=dict(
            cached.categories
            or {}
        ),
        category_scores={
            str(key): float(value)
            for key, value in (
                cached.category_scores
                or {}
            ).items()
        },
        applied_input_types=dict(
            cached.applied_input_types
            or {}
        ),
        provider=cached.provider,
        model=cached.provider_model,
        response_id=(
            cached.provider_response_id
        ),
        cached=True,
    )


def _save_analysis_cache(
    *,
    input_hash: str,
    result: ProviderModerationResult,
) -> None:
    defaults = {
        "provider_response_id": (
            result.response_id
        ),
        "flagged": (
            result.flagged
        ),
        "categories": (
            result.categories
        ),
        "category_scores": (
            result.category_scores
        ),
        "applied_input_types": (
            result.applied_input_types
        ),
        "last_accessed_at": (
            timezone.now()
        ),
        "expires_at": (
            _cache_expiry()
        ),
    }

    try:
        with transaction.atomic():
            (
                ContentSafetyAnalysisCache.objects
                .update_or_create(
                    input_type=SafetyInputType.TEXT,
                    input_hash=input_hash,
                    provider=result.provider,
                    provider_model=result.model,
                    defaults=defaults,
                )
            )

    except IntegrityError:
        logger.info(
            "[content_safety] cache race "
            "input_hash=%s",
            input_hash[:12],
        )


def _record_actionable_event(
    *,
    actor,
    context: str,
    field_name: str,
    input_hash: str,
    result: TextSafetyResult,
) -> None:
    if result.decision == SafetyDecision.ALLOW:
        return

    try:
        ContentSafetyEvent.objects.create(
            actor=(
                actor
                if getattr(
                    actor,
                    "pk",
                    None,
                )
                else None
            ),
            input_type=SafetyInputType.TEXT,
            input_hash=input_hash,
            context=context,
            field_name=str(
                field_name
                or ""
            )[:80],
            decision=result.decision,
            risk_level=result.risk_level,
            reason_code=result.reason_code,
            policy_version=(
                settings.CONTENT_SAFETY_POLICY_VERSION
            ),
            provider=result.provider,
            provider_model=result.provider_model,
            provider_flagged=(
                result.provider_flagged
            ),
            adjudicated=(
                result.adjudicated
            ),
            adjudication_model=(
                result.adjudication_model
            ),
        )

    except Exception:
        logger.exception(
            "[content_safety] failed to record event "
            "context=%s input_hash=%s",
            context,
            input_hash[:12],
        )


def check_text_safety(
    *,
    text,
    context: str,
    actor=None,
    field_name: str = "",
    record_event: bool = True,
) -> TextSafetyResult:
    """
    Evaluate user text before publication.
    """

    normalized_text = normalize_text_for_safety(
        text
    )

    input_hash = hash_safety_input(
        normalized_text
    )

    if not normalized_text:
        return TextSafetyResult(
            decision=SafetyDecision.ALLOW,
            risk_level=SafetyRiskLevel.LOW,
            reason_code=SafetyReason.SAFE,
            input_hash=input_hash,
        )

    max_chars = int(
        settings.CONTENT_SAFETY_MAX_TEXT_CHARS
    )

    if len(
        normalized_text
    ) > max_chars:
        raise ValueError(
            "Text exceeds the content safety inspection limit."
        )

    normalized_context = _normalize_context(
        context
    )

    if not settings.CONTENT_SAFETY_ENABLED:
        return TextSafetyResult(
            decision=SafetyDecision.ALLOW,
            risk_level=SafetyRiskLevel.LOW,
            reason_code=SafetyReason.SAFE,
            input_hash=input_hash,
        )

    local_signals = inspect_local_text_signals(
        text=normalized_text
    )

    supplemental_signals = (
        _sexual_language_signals(
            normalized_text
        )
    )

    local_signal_values = list(
        dict.fromkeys(
            [
                *list(
                    local_signals.reasons
                ),
                *list(
                    supplemental_signals
                ),
            ]
        )
    )

    provider = OpenAIModerationProvider()

    moderation = _get_cached_analysis(
        input_hash=input_hash,
        provider_name=provider.provider_name,
        provider_model=provider.model,
    )

    if moderation is None:
        try:
            moderation = provider.moderate_text(
                text=normalized_text
            )

            _save_analysis_cache(
                input_hash=input_hash,
                result=moderation,
            )

        except Exception as exc:
            logger.exception(
                "[content_safety] moderation failed "
                "context=%s input_hash=%s",
                normalized_context,
                input_hash[:12],
            )

            raise ContentSafetyUnavailableError() from exc

    force_contextual_review = (
        _should_force_adjudication(
            context=normalized_context
        )
        or bool(
            supplemental_signals
        )
    )

    policy = evaluate_text_policy(
        moderation=moderation,
        local_signals=local_signals,
        force_contextual_review=(
            force_contextual_review
        ),
        context=normalized_context,
    )

    decision = str(
        policy.decision
    )

    risk_level = str(
        policy.risk_level
    )

    reason_code = str(
        policy.reason_code
    )

    adjudicated = False
    adjudication_model = ""
    adjudication_cached = False

    if policy.requires_adjudication:
        if not settings.CONTENT_SAFETY_ADJUDICATION_ENABLED:
            decision = SafetyDecision.REVIEW
            risk_level = SafetyRiskLevel.MEDIUM
            reason_code = (
                SafetyReason.ADJUDICATION_REQUIRED
            )

        else:
            active_categories = (
                active_moderation_categories(
                    moderation
                )
            )

            adjudication_model = (
                settings.CONTENT_SAFETY_ADJUDICATION_MODEL
            )

            cached_adjudication = (
                get_cached_adjudication(
                    input_hash=input_hash,
                    context=normalized_context,
                    active_categories=active_categories,
                    local_signals=local_signal_values,
                    model=adjudication_model,
                )
            )

            if cached_adjudication is not None:
                decision = cached_adjudication[
                    "decision"
                ]

                risk_level = cached_adjudication[
                    "risk_level"
                ]

                reason_code = cached_adjudication[
                    "reason_code"
                ]

                adjudicated = True
                adjudication_cached = True

                adjudication_model = (
                    cached_adjudication[
                        "model"
                    ]
                )

            else:
                try:
                    adjudication = adjudicate_text(
                        text=normalized_text,
                        context=normalized_context,
                        active_categories=active_categories,
                        local_signals=local_signal_values,
                    )

                    decision = adjudication[
                        "decision"
                    ]

                    risk_level = adjudication[
                        "risk_level"
                    ]

                    reason_code = adjudication[
                        "reason_code"
                    ]

                    adjudicated = True

                    adjudication_model = (
                        adjudication[
                            "model"
                        ]
                    )

                    cache_adjudication(
                        input_hash=input_hash,
                        context=normalized_context,
                        active_categories=active_categories,
                        local_signals=local_signal_values,
                        model=adjudication_model,
                        decision=decision,
                        risk_level=risk_level,
                        reason_code=reason_code,
                    )

                except Exception:
                    logger.exception(
                        "[content_safety] adjudication failed "
                        "context=%s input_hash=%s",
                        normalized_context,
                        input_hash[:12],
                    )

                    decision = SafetyDecision.REVIEW
                    risk_level = SafetyRiskLevel.MEDIUM
                    reason_code = (
                        SafetyReason.ADJUDICATION_REQUIRED
                    )

    result = TextSafetyResult(
        decision=decision,
        risk_level=risk_level,
        reason_code=reason_code,
        input_hash=input_hash,
        provider=moderation.provider,
        provider_model=moderation.model,
        provider_flagged=moderation.flagged,
        categories=moderation.categories,
        category_scores=moderation.category_scores,
        local_signals=tuple(
            local_signal_values
        ),
        cached=moderation.cached,
        adjudicated=adjudicated,
        adjudication_model=adjudication_model,
        adjudication_cached=adjudication_cached,
    )

    if record_event:
        _record_actionable_event(
            actor=actor,
            context=normalized_context,
            field_name=field_name,
            input_hash=input_hash,
            result=result,
        )

    return result


def enforce_text_safety(
    *,
    text,
    context: str,
    actor=None,
    field_name: str = "",
    record_event: bool = True,
) -> TextSafetyResult:
    """
    Require text to pass before publication.
    """

    result = check_text_safety(
        text=text,
        context=context,
        actor=actor,
        field_name=field_name,
        record_event=record_event,
    )

    if result.decision == SafetyDecision.BLOCK:
        raise ContentSafetyBlockedError(
            reason_code=result.reason_code
        )

    if result.decision == SafetyDecision.REVIEW:
        raise ContentSafetyReviewError(
            reason_code=result.reason_code
        )

    return result
# apps/content_safety/services/image.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

import base64
import hashlib
import logging
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
from apps.content_safety.services.adjudication_cache import (
    cache_adjudication,
    get_cached_adjudication,
)
from apps.content_safety.services.image_adjudication import (
    adjudicate_image,
)
from apps.content_safety.services.image_guard import (
    inspect_image_guard,
)
from apps.content_safety.services.media_types import (
    ImageSafetyResult,
)
from apps.content_safety.services.policy import (
    active_moderation_categories_for_input,
    evaluate_image_policy,
)
from apps.content_safety.services.providers.openai_moderation import (
    OpenAIModerationProvider,
)
from apps.content_safety.services.types import (
    ProviderModerationResult,
)


logger = logging.getLogger(
    __name__
)


# GIF is intentionally excluded from the direct safety core.
# Animated media must be canonicalized before inspection so hidden frames
# cannot bypass publication safety.
_SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


_IMAGE_GUARD_CACHE_SIGNAL = (
    "image_guard_v1"
)

_IMAGE_FINAL_CACHE_SIGNAL = (
    "image_final_adjudication_v1"
)


def _cache_expiry():
    return timezone.now() + timedelta(
        days=settings.CONTENT_SAFETY_CACHE_TTL_DAYS
    )


def _media_policy_version() -> str:
    value = str(
        settings.CONTENT_SAFETY_MEDIA_POLICY_VERSION
        or ""
    ).strip()

    if not value:
        raise RuntimeError(
            "CONTENT_SAFETY_MEDIA_POLICY_VERSION is missing."
        )

    return value


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


def _normalize_declared_mime_type(
    value: str | None,
) -> str:
    normalized = str(
        value
        or ""
    ).strip().lower()

    if normalized == "image/jpg":
        return "image/jpeg"

    if normalized in {
        "application/octet-stream",
        "binary/octet-stream",
    }:
        return ""

    return normalized


def _detect_image_mime_type(
    image_bytes: bytes,
) -> str | None:
    if image_bytes.startswith(
        b"\xff\xd8\xff"
    ):
        return "image/jpeg"

    if image_bytes.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        return "image/png"

    if (
        len(image_bytes) >= 12
        and image_bytes[
            0:4
        ] == b"RIFF"
        and image_bytes[
            8:12
        ] == b"WEBP"
    ):
        return "image/webp"

    if image_bytes.startswith(
        (
            b"GIF87a",
            b"GIF89a",
        )
    ):
        return "image/gif"

    return None


def _resolve_image_mime_type(
    *,
    image_bytes: bytes,
    declared_mime_type: str | None,
) -> str:
    actual = _detect_image_mime_type(
        image_bytes
    )

    if actual is None:
        raise ValueError(
            "Unsupported or unrecognized image format."
        )

    if actual == "image/gif":
        raise ValueError(
            "GIF images must be canonicalized to a static supported "
            "image before content safety inspection."
        )

    if actual not in _SUPPORTED_IMAGE_MIME_TYPES:
        raise ValueError(
            "Unsupported image type for content safety."
        )

    declared = _normalize_declared_mime_type(
        declared_mime_type
    )

    if (
        declared
        and declared != actual
    ):
        raise ValueError(
            "Declared image type does not match the actual file format."
        )

    return actual


def _normalize_image_bytes(
    value,
) -> bytes:
    if isinstance(
        value,
        bytes,
    ):
        image_bytes = value

    elif isinstance(
        value,
        bytearray,
    ):
        image_bytes = bytes(
            value
        )

    elif isinstance(
        value,
        memoryview,
    ):
        image_bytes = value.tobytes()

    else:
        raise TypeError(
            "image_bytes must be bytes-like."
        )

    if not image_bytes:
        raise ValueError(
            "Image content is empty."
        )

    max_bytes = int(
        settings.CONTENT_SAFETY_MAX_IMAGE_BYTES
    )

    if max_bytes <= 0:
        raise RuntimeError(
            "CONTENT_SAFETY_MAX_IMAGE_BYTES must be positive."
        )

    if len(
        image_bytes
    ) > max_bytes:
        raise ValueError(
            "Image exceeds the content safety inspection size limit."
        )

    return image_bytes


def _hash_image_bytes(
    image_bytes: bytes,
) -> str:
    return hashlib.sha256(
        image_bytes
    ).hexdigest()


def _image_data_url(
    *,
    image_bytes: bytes,
    mime_type: str,
) -> str:
    encoded = base64.b64encode(
        image_bytes
    ).decode(
        "ascii"
    )

    return (
        f"data:{mime_type};base64,{encoded}"
    )


def _get_cached_analysis(
    *,
    input_hash: str,
    provider_name: str,
    provider_model: str,
) -> ProviderModerationResult | None:
    cached = (
        ContentSafetyAnalysisCache.objects
        .filter(
            input_type=SafetyInputType.IMAGE,
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
                    input_type=SafetyInputType.IMAGE,
                    input_hash=input_hash,
                    provider=result.provider,
                    provider_model=result.model,
                    defaults=defaults,
                )
            )

    except IntegrityError:
        logger.info(
            "[content_safety] image analysis cache race "
            "input_hash=%s",
            input_hash[:12],
        )


def _record_actionable_event(
    *,
    actor,
    context: str,
    field_name: str,
    input_hash: str,
    result: ImageSafetyResult,
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
            input_type=SafetyInputType.IMAGE,
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
                _media_policy_version()
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
            "[content_safety] failed to record image event "
            "context=%s input_hash=%s",
            context,
            input_hash[:12],
        )


def _get_cached_guard(
    *,
    input_hash: str,
    context: str,
    model: str,
) -> dict | None:
    return get_cached_adjudication(
        input_hash=input_hash,
        context=context,
        active_categories=[],
        local_signals=[
            _IMAGE_GUARD_CACHE_SIGNAL,
        ],
        model=model,
        policy_version=(
            _media_policy_version()
        ),
    )


def _cache_guard(
    *,
    input_hash: str,
    context: str,
    model: str,
    decision: str,
    risk_level: str,
    reason_code: str,
) -> None:
    cache_adjudication(
        input_hash=input_hash,
        context=context,
        active_categories=[],
        local_signals=[
            _IMAGE_GUARD_CACHE_SIGNAL,
        ],
        model=model,
        decision=decision,
        risk_level=risk_level,
        reason_code=reason_code,
        policy_version=(
            _media_policy_version()
        ),
    )


def _final_cache_signals(
    *,
    guard_reason_code: str,
) -> list[str]:
    values = [
        _IMAGE_FINAL_CACHE_SIGNAL,
    ]

    normalized_guard_reason = str(
        guard_reason_code
        or ""
    ).strip()

    if normalized_guard_reason:
        values.append(
            f"guard:{normalized_guard_reason}"
        )

    return values


def check_image_safety(
    *,
    image_bytes,
    mime_type: str | None,
    context: str,
    actor=None,
    field_name: str = "",
    run_guard: bool = True,
    resolve_adjudication: bool = True,
    record_event: bool = True,
) -> ImageSafetyResult:
    """
    Evaluate one canonical image before publication.

    Flow:
    1. Validate and hash bytes.
    2. Reuse provider moderation cache when possible.
    3. Run free image moderation.
    4. For clean images, run the inexpensive vision guard.
    5. Escalate provider-flagged or guard-suspicious images to final adjudication.
    6. Fail closed when required safety analysis cannot complete.
    """

    normalized_bytes = _normalize_image_bytes(
        image_bytes
    )

    resolved_mime_type = _resolve_image_mime_type(
        image_bytes=normalized_bytes,
        declared_mime_type=mime_type,
    )

    input_hash = _hash_image_bytes(
        normalized_bytes
    )

    normalized_context = _normalize_context(
        context
    )

    if not settings.CONTENT_SAFETY_ENABLED:
        return ImageSafetyResult(
            decision=SafetyDecision.ALLOW,
            risk_level=SafetyRiskLevel.LOW,
            reason_code=SafetyReason.SAFE,
            input_hash=input_hash,
        )

    provider = OpenAIModerationProvider()

    moderation = _get_cached_analysis(
        input_hash=input_hash,
        provider_name=provider.provider_name,
        provider_model=provider.model,
    )

    image_data_url: str | None = None

    if moderation is None:
        image_data_url = _image_data_url(
            image_bytes=normalized_bytes,
            mime_type=resolved_mime_type,
        )

        try:
            moderation = provider.moderate_image_data_url(
                image_data_url=image_data_url
            )

            _save_analysis_cache(
                input_hash=input_hash,
                result=moderation,
            )

        except Exception as exc:
            logger.exception(
                "[content_safety] image moderation failed "
                "context=%s input_hash=%s",
                normalized_context,
                input_hash[:12],
            )

            raise ContentSafetyUnavailableError() from exc

    active_categories = (
        active_moderation_categories_for_input(
            moderation,
            input_type="image",
        )
    )

    policy = evaluate_image_policy(
        moderation=moderation,
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

    guarded = False
    guard_model = ""
    guard_decision = ""
    guard_reason_code = ""
    guard_cached = False

    adjudicated = False
    adjudication_model = ""
    adjudication_cached = False

    requires_final_adjudication = bool(
        policy.requires_adjudication
    )

    # ------------------------------------------------------------------
    # Cheap visual guard for provider-clean images
    # ------------------------------------------------------------------

    if (
        not requires_final_adjudication
        and run_guard
        and getattr(
            settings,
            "CONTENT_SAFETY_IMAGE_GUARD_ENABLED",
            True,
        )
    ):
        guarded = True

        guard_model = str(
            settings.CONTENT_SAFETY_IMAGE_GUARD_MODEL
        ).strip()

        cached_guard = _get_cached_guard(
            input_hash=input_hash,
            context=normalized_context,
            model=guard_model,
        )

        if cached_guard is not None:
            guard_decision = cached_guard[
                "decision"
            ]

            guard_reason_code = cached_guard[
                "reason_code"
            ]

            guard_cached = True

        else:
            if image_data_url is None:
                image_data_url = _image_data_url(
                    image_bytes=normalized_bytes,
                    mime_type=resolved_mime_type,
                )

            try:
                guard_result = inspect_image_guard(
                    image_data_url=image_data_url,
                    context=normalized_context,
                )

                guard_decision = guard_result[
                    "decision"
                ]

                guard_reason_code = guard_result[
                    "reason_code"
                ]

                guard_model = guard_result[
                    "model"
                ]

                _cache_guard(
                    input_hash=input_hash,
                    context=normalized_context,
                    model=guard_model,
                    decision=guard_result[
                        "decision"
                    ],
                    risk_level=guard_result[
                        "risk_level"
                    ],
                    reason_code=guard_result[
                        "reason_code"
                    ],
                )

            except Exception:
                logger.exception(
                    "[content_safety] image guard failed "
                    "context=%s input_hash=%s",
                    normalized_context,
                    input_hash[:12],
                )

                # The inexpensive guard is supplemental.
                # Escalate to the stronger final adjudicator rather than
                # immediately failing the publication.
                guard_decision = (
                    SafetyDecision.REVIEW
                )

                guard_reason_code = (
                    SafetyReason.ADJUDICATION_REQUIRED
                )

        if guard_decision == SafetyDecision.REVIEW:
            requires_final_adjudication = True

            decision = SafetyDecision.REVIEW
            risk_level = SafetyRiskLevel.HIGH
            reason_code = (
                guard_reason_code
                or SafetyReason.ADJUDICATION_REQUIRED
            )

    # ------------------------------------------------------------------
    # Final contextual image adjudication
    # ------------------------------------------------------------------

    if (
        requires_final_adjudication
        and resolve_adjudication
    ):
        if not settings.CONTENT_SAFETY_ADJUDICATION_ENABLED:
            decision = SafetyDecision.REVIEW
            risk_level = SafetyRiskLevel.MEDIUM
            reason_code = (
                SafetyReason.ADJUDICATION_REQUIRED
            )

        else:
            adjudication_model = str(
                settings.CONTENT_SAFETY_ADJUDICATION_MODEL
            ).strip()

            final_signals = _final_cache_signals(
                guard_reason_code=guard_reason_code
            )

            cached_adjudication = (
                get_cached_adjudication(
                    input_hash=input_hash,
                    context=normalized_context,
                    active_categories=active_categories,
                    local_signals=final_signals,
                    model=adjudication_model,
                    policy_version=(
                        _media_policy_version()
                    ),
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
                if image_data_url is None:
                    image_data_url = _image_data_url(
                        image_bytes=normalized_bytes,
                        mime_type=resolved_mime_type,
                    )

                try:
                    adjudication = adjudicate_image(
                        image_data_url=image_data_url,
                        context=normalized_context,
                        active_categories=active_categories,
                        guard_reason_code=guard_reason_code,
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
                        local_signals=final_signals,
                        model=adjudication_model,
                        decision=decision,
                        risk_level=risk_level,
                        reason_code=reason_code,
                        policy_version=(
                            _media_policy_version()
                        ),
                    )

                except Exception:
                    logger.exception(
                        "[content_safety] image adjudication failed "
                        "context=%s input_hash=%s",
                        normalized_context,
                        input_hash[:12],
                    )

                    # Fail closed:
                    # unpublished content stays unpublished when final
                    # contextual adjudication cannot complete.
                    decision = SafetyDecision.REVIEW
                    risk_level = SafetyRiskLevel.MEDIUM
                    reason_code = (
                        SafetyReason.ADJUDICATION_REQUIRED
                    )

    result = ImageSafetyResult(
        decision=decision,
        risk_level=risk_level,
        reason_code=reason_code,
        input_hash=input_hash,
        provider=moderation.provider,
        provider_model=moderation.model,
        provider_flagged=moderation.flagged,
        categories=moderation.categories,
        category_scores=moderation.category_scores,
        cached=moderation.cached,
        guarded=guarded,
        guard_model=guard_model,
        guard_decision=guard_decision,
        guard_reason_code=guard_reason_code,
        guard_cached=guard_cached,
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


def enforce_image_safety(
    *,
    image_bytes,
    mime_type: str | None,
    context: str,
    actor=None,
    field_name: str = "",
) -> ImageSafetyResult:
    """
    Require one canonical image to pass before publication.
    """

    result = check_image_safety(
        image_bytes=image_bytes,
        mime_type=mime_type,
        context=context,
        actor=actor,
        field_name=field_name,
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


def _read_image_file_bytes(
    *,
    file_obj,
) -> bytes:
    if file_obj is None:
        raise ValueError(
            "Image file is required."
        )

    max_bytes = int(
        settings.CONTENT_SAFETY_MAX_IMAGE_BYTES
    )

    known_size = getattr(
        file_obj,
        "size",
        None,
    )

    if (
        isinstance(
            known_size,
            int,
        )
        and known_size > max_bytes
    ):
        raise ValueError(
            "Image exceeds the content safety inspection size limit."
        )

    original_position: int | None = None
    opened_here = False

    try:
        try:
            original_position = file_obj.tell()
        except Exception:
            original_position = None

        is_closed = bool(
            getattr(
                file_obj,
                "closed",
                False,
            )
        )

        if (
            is_closed
            and hasattr(
                file_obj,
                "open",
            )
        ):
            file_obj.open(
                "rb"
            )
            opened_here = True

        if hasattr(
            file_obj,
            "seek",
        ):
            file_obj.seek(
                0
            )

        data = file_obj.read(
            max_bytes + 1
        )

        if len(
            data
        ) > max_bytes:
            raise ValueError(
                "Image exceeds the content safety inspection size limit."
            )

        return bytes(
            data
        )

    finally:
        if opened_here:
            try:
                file_obj.close()
            except Exception:
                pass

        elif (
            original_position is not None
            and hasattr(
                file_obj,
                "seek",
            )
        ):
            try:
                file_obj.seek(
                    original_position
                )
            except Exception:
                pass


def check_image_file_safety(
    *,
    file_obj,
    context: str,
    actor=None,
    field_name: str = "",
    mime_type: str | None = None,
) -> ImageSafetyResult:
    """
    Inspect one Django uploaded/stored canonical image.
    """

    resolved_mime_type = (
        mime_type
        or getattr(
            file_obj,
            "content_type",
            None,
        )
    )

    image_bytes = _read_image_file_bytes(
        file_obj=file_obj
    )

    return check_image_safety(
        image_bytes=image_bytes,
        mime_type=resolved_mime_type,
        context=context,
        actor=actor,
        field_name=field_name,
    )


def enforce_image_file_safety(
    *,
    file_obj,
    context: str,
    actor=None,
    field_name: str = "",
    mime_type: str | None = None,
) -> ImageSafetyResult:
    """
    Require one Django uploaded/stored canonical image to pass.
    """

    resolved_mime_type = (
        mime_type
        or getattr(
            file_obj,
            "content_type",
            None,
        )
    )

    image_bytes = _read_image_file_bytes(
        file_obj=file_obj
    )

    return enforce_image_safety(
        image_bytes=image_bytes,
        mime_type=resolved_mime_type,
        context=context,
        actor=actor,
        field_name=field_name,
    )
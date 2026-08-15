# apps/content_safety/services/video_visual.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

import json
from typing import Literal

from django.conf import settings
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from apps.content_safety.enums import (
    SafetyDecision,
    SafetyReason,
    SafetyRiskLevel,
)
from apps.content_safety.services.image_rules import (
    image_context_guidance,
    normalize_image_reason_code,
)


class VideoVisualGuardAssessment(BaseModel):
    decision: Literal[
        "allow",
        "review",
    ]

    risk_level: Literal[
        "low",
        "medium",
        "high",
        "critical",
    ]

    reason_code: str

    suspicious_frame_indices: list[int] = []


class VideoVisualAdjudication(BaseModel):
    decision: Literal[
        "allow",
        "block",
    ]

    risk_level: Literal[
        "low",
        "medium",
        "high",
        "critical",
    ]

    reason_code: str


def _normalize_detail(
    value: str,
    *,
    fallback: str,
) -> str:
    normalized = str(
        value
        or fallback
    ).strip().lower()

    if normalized not in {
        "low",
        "high",
        "auto",
    }:
        return fallback

    return normalized


def _extract_content(
    response,
) -> str:
    try:
        return str(
            response.choices[
                0
            ].message.content
            or ""
        ).strip()

    except Exception:
        return ""


def _frame_content(
    *,
    frame_data_urls: list[tuple[int, str]],
    detail: str,
) -> list[dict]:
    content: list[dict] = []

    for frame_index, data_url in frame_data_urls:
        content.append(
            {
                "type": "text",
                "text": (
                    f"VIDEO SAMPLE FRAME INDEX: {frame_index}"
                ),
            }
        )

        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": data_url,
                    "detail": detail,
                },
            }
        )

    return content


def _normalize_indices(
    values,
    *,
    valid_indices: set[int],
) -> list[int]:
    resolved: list[int] = []

    for value in values or []:
        try:
            index = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if index not in valid_indices:
            continue

        if index in resolved:
            continue

        resolved.append(
            index
        )

    return resolved


def inspect_video_visual_guard(
    *,
    frame_data_urls: list[tuple[int, str]],
    context: str,
) -> dict:
    """
    Screen all sampled video frames in one inexpensive vision request.

    The guard never blocks directly.
    """

    if not frame_data_urls:
        raise ValueError(
            "Video visual guard requires frames."
        )

    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is missing."
        )

    model = str(
        settings.CONTENT_SAFETY_VIDEO_VISUAL_GUARD_MODEL
    ).strip()

    detail = _normalize_detail(
        settings.CONTENT_SAFETY_VIDEO_VISUAL_GUARD_DETAIL,
        fallback="low",
    )

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=(
            settings.CONTENT_SAFETY_IMAGE_GUARD_TIMEOUT_SECONDS
        ),
        max_retries=(
            settings.CONTENT_SAFETY_OPENAI_MAX_RETRIES
        ),
    )

    system_prompt = (
        "You are TownLIT's low-cost sampled-video visual safety guard.\n"
        "You are seeing multiple sampled frames from one user video.\n"
        "Your task is NOT to make a final blocking decision.\n\n"

        "Return REVIEW if ANY sampled frame may contain:\n"
        "- pornography or explicit sexual imagery\n"
        "- sexualized nudity\n"
        "- possible sexualization or exploitation of a child or minor\n"
        "- a sexualized person whose age is materially uncertain\n"
        "- graphic gore or gratuitous severe bodily injury\n"
        "- visual encouragement of suicide or serious self-harm\n"
        "- visual encouragement or glorification of serious violence\n"
        "- hate propaganda or dehumanizing visual messaging\n"
        "- dangerous visual instructions\n"
        "- visible text that itself contains materially unsafe content\n"
        "- anything genuinely uncertain that requires stronger review\n\n"

        "ALLOW ordinary social content, portraits, family images, children "
        "in normal non-sexual settings, travel, worship, ministry, food, "
        "fitness, nature, art, education, medical recovery, historical, "
        "documentary, pastoral, and legitimate survivor-support imagery.\n\n"

        "A video frame may be taken out of temporal context. Do not treat "
        "legitimate documentary, medical, historical, biblical, recovery, "
        "or awareness imagery as endorsement merely because it depicts a "
        "sensitive subject.\n\n"

        + image_context_guidance(
            context
        )
        + "\n"

        "Return suspicious_frame_indices using the exact integer indices "
        "shown immediately before the relevant frame images.\n\n"

        "Use ONLY these reason_code values:\n"
        "- safe\n"
        "- harassment\n"
        "- harassment_threatening\n"
        "- hate\n"
        "- hate_threatening\n"
        "- sexual\n"
        "- sexual_explicit\n"
        "- sexual_minors\n"
        "- self_harm\n"
        "- self_harm_intent\n"
        "- self_harm_instructions\n"
        "- violence\n"
        "- violence_graphic\n"
        "- provider_flagged\n"
        "- adjudication_required\n\n"

        "Return valid JSON only:\n"
        "{\n"
        '  "decision": "allow | review",\n'
        '  "risk_level": "low | medium | high | critical",\n'
        '  "reason_code": "one allowed reason code",\n'
        '  "suspicious_frame_indices": [0, 2]\n'
        "}"
    )

    user_content = [
        {
            "type": "text",
            "text": (
                f"Publication context: {context}\n"
                "Inspect all attached sampled frames from this video."
            ),
        },
        *_frame_content(
            frame_data_urls=frame_data_urls,
            detail=detail,
        ),
    ]

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        response_format={
            "type": "json_object",
        },
    )

    raw_content = _extract_content(
        response
    )

    if not raw_content:
        raise RuntimeError(
            "Video visual guard returned empty content."
        )

    try:
        payload = json.loads(
            raw_content
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Video visual guard returned invalid JSON."
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Video visual guard returned an invalid payload."
        )

    payload[
        "reason_code"
    ] = normalize_image_reason_code(
        payload.get(
            "reason_code",
            "",
        )
    )

    try:
        parsed = VideoVisualGuardAssessment.model_validate(
            payload
        )

    except ValidationError as exc:
        raise RuntimeError(
            "Video visual guard returned an invalid schema."
        ) from exc

    valid_indices = {
        index
        for index, _ in frame_data_urls
    }

    indices = _normalize_indices(
        parsed.suspicious_frame_indices,
        valid_indices=valid_indices,
    )

    if parsed.decision == SafetyDecision.ALLOW:
        return {
            "decision": SafetyDecision.ALLOW,
            "risk_level": SafetyRiskLevel.LOW,
            "reason_code": SafetyReason.SAFE,
            "suspicious_frame_indices": [],
            "model": model,
        }

    return {
        "decision": SafetyDecision.REVIEW,
        "risk_level": parsed.risk_level,
        "reason_code": normalize_image_reason_code(
            parsed.reason_code
        ),
        "suspicious_frame_indices": indices,
        "model": model,
    }


def adjudicate_video_visual(
    *,
    frame_data_urls: list[tuple[int, str]],
    context: str,
    provider_reason_codes: list[str],
    guard_reason_code: str = "",
) -> dict:
    """
    Make the final contextual visual decision for sampled video frames.
    """

    if not frame_data_urls:
        raise ValueError(
            "Video visual adjudication requires frames."
        )

    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is missing."
        )

    model = str(
        settings.CONTENT_SAFETY_VIDEO_VISUAL_ADJUDICATION_MODEL
    ).strip()

    detail = _normalize_detail(
        settings.CONTENT_SAFETY_VIDEO_VISUAL_ADJUDICATION_DETAIL,
        fallback="high",
    )

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=(
            settings.CONTENT_SAFETY_ADJUDICATION_TIMEOUT_SECONDS
        ),
        max_retries=(
            settings.CONTENT_SAFETY_OPENAI_MAX_RETRIES
        ),
    )

    provider_text = (
        ", ".join(
            sorted(
                {
                    str(item).strip()
                    for item in provider_reason_codes
                    if str(item).strip()
                }
            )
        )
        or "none"
    )

    guard_text = (
        str(
            guard_reason_code
            or ""
        ).strip()
        or "none"
    )

    system_prompt = (
        "You are TownLIT's final sampled-video visual safety adjudicator.\n"
        "Evaluate the attached sampled frames in their publication context.\n\n"

        "BLOCK if the sampled visual content materially contains or promotes:\n"
        "- pornography or explicit sexual imagery\n"
        "- sexualized nudity or sexual exploitation\n"
        "- sexualization or exploitation of a child or minor\n"
        "- gratuitous graphic gore primarily intended to shock\n"
        "- encouragement or glorification of suicide or serious self-harm\n"
        "- encouragement or glorification of serious violence\n"
        "- hate propaganda or dehumanizing visual messaging\n"
        "- materially dangerous visual instructions\n"
        "- other clearly unsafe visual content unsuitable for publication\n\n"

        "ALLOW legitimate:\n"
        "- normal portraits, selfies, families, children in ordinary settings\n"
        "- worship, ministry, travel, food, fitness, nature, and art\n"
        "- non-gratuitous medical or recovery imagery\n"
        "- historical or documentary material\n"
        "- survivor-support and awareness material\n"
        "- educational and safety material\n"
        "- biblical/religious imagery including non-gratuitous crucifixion art\n\n"

        "Do not equate depiction with endorsement. Judge the actual purpose "
        "and context visible in the sampled frames.\n\n"

        + image_context_guidance(
            context
        )
        + "\n"

        "Use ONLY these reason_code values:\n"
        "- safe\n"
        "- harassment\n"
        "- harassment_threatening\n"
        "- hate\n"
        "- hate_threatening\n"
        "- sexual\n"
        "- sexual_explicit\n"
        "- sexual_minors\n"
        "- self_harm\n"
        "- self_harm_intent\n"
        "- self_harm_instructions\n"
        "- violence\n"
        "- violence_graphic\n"
        "- provider_flagged\n"
        "- adjudication_required\n\n"

        "Return valid JSON only:\n"
        "{\n"
        '  "decision": "allow | block",\n'
        '  "risk_level": "low | medium | high | critical",\n'
        '  "reason_code": "one allowed reason code"\n'
        "}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"PUBLICATION CONTEXT:\n{context}\n\n"
                            f"PROVIDER SIGNALS:\n{provider_text}\n\n"
                            f"VIDEO GUARD SIGNAL:\n{guard_text}\n\n"
                            "Make the final visual publication decision."
                        ),
                    },
                    *_frame_content(
                        frame_data_urls=frame_data_urls,
                        detail=detail,
                    ),
                ],
            },
        ],
        response_format={
            "type": "json_object",
        },
    )

    raw_content = _extract_content(
        response
    )

    if not raw_content:
        raise RuntimeError(
            "Video visual adjudication returned empty content."
        )

    try:
        payload = json.loads(
            raw_content
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Video visual adjudication returned invalid JSON."
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Video visual adjudication returned invalid payload."
        )

    payload[
        "reason_code"
    ] = normalize_image_reason_code(
        payload.get(
            "reason_code",
            "",
        )
    )

    try:
        parsed = VideoVisualAdjudication.model_validate(
            payload
        )

    except ValidationError as exc:
        raise RuntimeError(
            "Video visual adjudication returned invalid schema."
        ) from exc

    return {
        "decision": str(
            parsed.decision
        ),
        "risk_level": str(
            parsed.risk_level
        ),
        "reason_code": normalize_image_reason_code(
            parsed.reason_code
        ),
        "model": model,
    }
# apps/content_safety/services/image_guard.py
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
    SafetyReason,
)
from apps.content_safety.services.image_rules import (
    image_context_guidance,
    normalize_image_reason_code,
)


class ImageGuardAssessment(BaseModel):
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


def _normalize_detail(
    value: str,
) -> str:
    normalized = str(
        value
        or "low"
    ).strip().lower()

    if normalized not in {
        "low",
        "high",
        "auto",
    }:
        return "low"

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


def _parse_guard_result(
    raw_content: str,
) -> ImageGuardAssessment:
    if not raw_content:
        raise RuntimeError(
            "Image guard returned empty content."
        )

    try:
        payload = json.loads(
            raw_content
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Image guard returned invalid JSON."
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Image guard returned an invalid payload."
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
        parsed = ImageGuardAssessment.model_validate(
            payload
        )

    except ValidationError as exc:
        raise RuntimeError(
            "Image guard returned an invalid schema."
        ) from exc

    if parsed.decision == "allow":
        return ImageGuardAssessment(
            decision="allow",
            risk_level="low",
            reason_code=str(
                SafetyReason.SAFE
            ),
        )

    return parsed


def inspect_image_guard(
    *,
    image_data_url: str,
    context: str,
) -> dict:
    """
    Run the inexpensive visual safety guard.

    The guard never blocks publication directly.
    It either allows the clean image or escalates it for final adjudication.
    """

    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is missing."
        )

    model = str(
        settings.CONTENT_SAFETY_IMAGE_GUARD_MODEL
    ).strip()

    if not model:
        raise RuntimeError(
            "Image safety guard model is missing."
        )

    detail = _normalize_detail(
        settings.CONTENT_SAFETY_IMAGE_GUARD_DETAIL
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
        "You are TownLIT's low-cost visual safety screening guard.\n"
        "Your task is NOT to make a final blocking decision.\n"
        "Return ALLOW only when the image appears safe for social publication.\n"
        "Return REVIEW whenever a stronger image adjudicator should inspect it.\n\n"

        "REVIEW if the image may contain any of the following:\n"
        "- pornography or explicit sexual imagery\n"
        "- sexualized nudity\n"
        "- possible sexualization or exploitation of a child or minor\n"
        "- a sexualized person whose age is materially uncertain\n"
        "- graphic gore or severe bodily injury presented gratuitously\n"
        "- imagery encouraging suicide or serious self-harm\n"
        "- imagery materially encouraging serious violence\n"
        "- clear hate propaganda or dehumanizing visual messaging\n"
        "- any other image where safety is genuinely uncertain\n\n"

        "ALLOW ordinary:\n"
        "- portraits, selfies, families, children in normal non-sexual contexts\n"
        "- swimwear or ordinary clothing when not sexualized\n"
        "- food, travel, nature, worship, ministry, art, fitness, and daily life\n"
        "- legitimate medical, historical, documentary, recovery, educational, "
        "or pastoral imagery when it is not exploitative or gratuitous\n"
        "- breastfeeding or ordinary caregiving when not sexualized\n"
        "- biblical or religious artwork, including non-gratuitous depictions "
        "of suffering or crucifixion\n\n"

        "If age or sexual context is uncertain, choose REVIEW rather than guessing.\n"
        "Do not infer harmful intent merely from skin exposure alone.\n\n"

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

        "Return valid JSON only.\n"
        "No markdown and no explanation.\n\n"

        "Required format:\n"
        "{\n"
        '  "decision": "allow | review",\n'
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
                            f"Publication context: {context}\n"
                            "Screen the attached image."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url,
                            "detail": detail,
                        },
                    },
                ],
            },
        ],
        response_format={
            "type": "json_object",
        },
    )

    parsed = _parse_guard_result(
        _extract_content(
            response
        )
    )

    return {
        "decision": parsed.decision,
        "risk_level": parsed.risk_level,
        "reason_code": normalize_image_reason_code(
            parsed.reason_code
        ),
        "model": model,
    }
# apps/content_safety/services/image_adjudication.py
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
    SafetyRiskLevel,
)
from apps.content_safety.services.image_rules import (
    image_context_guidance,
    normalize_image_reason_code,
)


class ImageSafetyAdjudication(BaseModel):
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
) -> str:
    normalized = str(
        value
        or "high"
    ).strip().lower()

    if normalized not in {
        "low",
        "high",
        "auto",
    }:
        return "high"

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


def _parse_adjudication(
    raw_content: str,
) -> ImageSafetyAdjudication:
    if not raw_content:
        raise RuntimeError(
            "Image safety adjudication returned empty content."
        )

    try:
        payload = json.loads(
            raw_content
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Image safety adjudication returned invalid JSON."
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Image safety adjudication returned an invalid payload."
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
        return ImageSafetyAdjudication.model_validate(
            payload
        )

    except ValidationError as exc:
        raise RuntimeError(
            "Image safety adjudication returned an invalid schema."
        ) from exc


def adjudicate_image(
    *,
    image_data_url: str,
    context: str,
    active_categories: list[str],
    guard_reason_code: str = "",
) -> dict:
    """
    Resolve final contextual TownLIT image safety.
    """

    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is missing."
        )

    model = str(
        settings.CONTENT_SAFETY_ADJUDICATION_MODEL
    ).strip()

    if not model:
        raise RuntimeError(
            "Image adjudication model is missing."
        )

    detail = _normalize_detail(
        settings.CONTENT_SAFETY_IMAGE_ADJUDICATION_DETAIL
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

    category_text = (
        ", ".join(
            active_categories
        )
        if active_categories
        else "none"
    )

    guard_text = (
        str(
            guard_reason_code
            or ""
        ).strip()
        or "none"
    )

    system_prompt = (
        "You are TownLIT's final contextual image safety adjudicator.\n"
        "TownLIT is a Christian social application with a respectful "
        "community standard.\n\n"

        "Evaluate the ACTUAL IMAGE and its publication context.\n"
        "Do not merely repeat moderation labels.\n"
        "Do not block legitimate sensitive material just because a difficult "
        "subject appears.\n\n"

        "BLOCK when the image materially contains or promotes:\n"
        "- pornography or explicit sexual imagery intended for arousal\n"
        "- sexualized nudity or sexual exploitation\n"
        "- sexualization, exploitation, grooming imagery, or sexual content "
        "involving a child or minor\n"
        "- gratuitous graphic gore primarily presented for shock\n"
        "- clear visual encouragement or glorification of suicide or serious self-harm\n"
        "- clear visual encouragement or glorification of serious violence\n"
        "- clear hate propaganda or dehumanizing visual messaging\n"
        "- other clearly unsafe visual content unsuitable for social publication\n\n"

        "ALLOW legitimate imagery such as:\n"
        "- normal portraits, selfies, family, worship, ministry, travel, food, "
        "fitness, nature, art, and everyday-life photography\n"
        "- children in ordinary non-sexual family, church, school, sports, "
        "or community settings\n"
        "- normal swimwear or skin exposure when it is not sexualized\n"
        "- breastfeeding and caregiving when not sexualized\n"
        "- non-gratuitous medical, injury, recovery, or survivor-support imagery\n"
        "- historical and documentary material\n"
        "- educational and safety-awareness material\n"
        "- biblical and religious artwork, including crucifixion imagery, "
        "when its purpose is not gratuitous shock\n\n"

        "IMPORTANT MINOR-SAFETY RULE:\n"
        "- If the image actually sexualizes or exploits a minor, BLOCK with "
        "reason_code sexual_minors.\n"
        "- Do not classify an ordinary image of a child as sexual merely because "
        "a child is present.\n"
        "- If explicit sexual content is present and age cannot safely be "
        "established, BLOCK because the explicit sexual content itself is "
        "not suitable for publication.\n\n"

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
        '  "decision": "allow | block",\n'
        '  "risk_level": "low | medium | high | critical",\n'
        '  "reason_code": "one allowed reason code"\n'
        "}"
    )

    user_text = (
        f"PUBLICATION CONTEXT:\n{context}\n\n"
        f"MODERATION SIGNALS:\n{category_text}\n\n"
        f"VISION GUARD SIGNAL:\n{guard_text}\n\n"
        "Make the final publication safety decision for the attached image."
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
                        "text": user_text,
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

    parsed = _parse_adjudication(
        _extract_content(
            response
        )
    )

    decision = str(
        parsed.decision
    )

    risk_level = str(
        parsed.risk_level
    )

    if decision not in {
        SafetyDecision.ALLOW,
        SafetyDecision.BLOCK,
    }:
        raise RuntimeError(
            "Invalid image adjudication decision."
        )

    if risk_level not in {
        SafetyRiskLevel.LOW,
        SafetyRiskLevel.MEDIUM,
        SafetyRiskLevel.HIGH,
        SafetyRiskLevel.CRITICAL,
    }:
        raise RuntimeError(
            "Invalid image adjudication risk level."
        )

    return {
        "decision": decision,
        "risk_level": risk_level,
        "reason_code": normalize_image_reason_code(
            parsed.reason_code
        ),
        "model": model,
    }
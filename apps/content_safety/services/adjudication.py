# apps/content_safety/services/adjudication.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

import json
import re
from typing import Literal

from django.conf import settings
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from apps.content_safety.enums import (
    SafetyContext,
    SafetyDecision,
    SafetyRiskLevel,
)


class TextSafetyAdjudication(BaseModel):
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


_ALLOWED_REASON_CODES = {
    "safe",
    "profanity",
    "abusive_language",
    "personal_attack",
    "bullying",
    "harassment",
    "harassment_threatening",
    "hate",
    "hate_threatening",
    "sexual",
    "sexual_explicit",
    "sexual_solicitation",
    "sexual_minors",
    "self_harm",
    "self_harm_intent",
    "self_harm_instructions",
    "violence",
    "violence_graphic",
    "illicit",
    "illicit_violent",
    "spam",
    "scam",
    "other_policy_violation",
}


_REASON_ALIASES = {
    # Self-harm
    "suicidal_ideation": "self_harm_intent",
    "suicide_ideation": "self_harm_intent",
    "suicidal_thoughts": "self_harm_intent",
    "suicide_intent": "self_harm_intent",
    "self_harm_ideation": "self_harm_intent",
    "self_harm_thoughts": "self_harm_intent",
    "suicide_instructions": "self_harm_instructions",
    "suicidal_instructions": "self_harm_instructions",

    # Abuse
    "verbal_abuse": "abusive_language",
    "vulgar_abuse": "abusive_language",
    "vulgar_language": "profanity",
    "obscene_language": "profanity",
    "insult": "personal_attack",
    "insults": "personal_attack",
    "targeted_insult": "personal_attack",
    "personal_insult": "personal_attack",

    # Sexual
    "explicit_sexual_content": "sexual_explicit",
    "sexual_content": "sexual",
    "sexualized_content": "sexual",
    "sexualized_language": "sexual",
    "sexual_request": "sexual_solicitation",
    "sexual_solicitation_request": "sexual_solicitation",
    "nude_request": "sexual_solicitation",
    "sexting_request": "sexual_solicitation",
    "child_sexual_content": "sexual_minors",
    "minor_sexual_content": "sexual_minors",
    "sexualization_of_minors": "sexual_minors",
    "sexual_exploitation_of_minors": "sexual_minors",

    # Violence
    "violent_threat": "harassment_threatening",
    "threat_of_violence": "harassment_threatening",
    "graphic_violence": "violence_graphic",

    # Hate
    "hate_speech": "hate",
    "violent_hate": "hate_threatening",

    # Illicit
    "criminal_instructions": "illicit",
    "violent_criminal_instructions": "illicit_violent",

    # Spam
    "scamming": "scam",
    "fraud": "scam",
}


def _context_value(
    value,
) -> str:
    raw_value = getattr(
        value,
        "value",
        value,
    )

    return str(
        raw_value
        or ""
    ).strip().lower()


def _context_guidance(
    context: str,
) -> str:
    """
    Return context-specific adjudication instructions.

    These instructions refine policy without changing the moderation model.
    """

    normalized = _context_value(
        context
    )

    testimony_context = _context_value(
        SafetyContext.TESTIMONY
    )

    prayer_context = _context_value(
        SafetyContext.PRAYER
    )

    journey_context = _context_value(
        SafetyContext.JOURNEY_TEXT
    )

    profile_context = _context_value(
        SafetyContext.PROFILE_TEXT
    )

    group_message_context = _context_value(
        SafetyContext.GROUP_MESSAGE
    )

    if normalized == testimony_context:
        return (
            "TESTIMONY-SPECIFIC RULES:\n"
            "- A personal testimony may recount painful or disturbing events.\n"
            "- Do NOT block merely because the author describes or reports "
            "past abuse, sexual victimization, domestic violence, threats, "
            "suicidal thoughts, self-harm history, addiction, pornography, "
            "crime, hatred, or other traumatic experiences.\n"
            "- Do NOT treat a threat quoted from an abuser as a threat made "
            "by the testimony author when the narrative clearly shows the "
            "author is recounting what happened.\n"
            "- Do NOT treat non-erotic discussion of childhood sexual abuse "
            "or exploitation as sexualization of minors.\n"
            "- Recovery, repentance, healing, faith, awareness, support-seeking, "
            "and victim-survivor narratives should normally be allowed.\n"
            "- Quoted offensive or vulgar language may be allowed when needed "
            "to explain a real event and the author is not endorsing it.\n"
            "- The Testimony context is NOT a blanket exemption. A short or "
            "standalone sexualized, threatening, hateful, or abusive statement "
            "with no genuine narrative context must still be judged normally.\n"
            "- BLOCK if the author is actually threatening or targeting another "
            "person, encouraging violence or self-harm, giving actionable harmful "
            "instructions, sexually soliciting someone, promoting hatred, "
            "sexualizing or exploiting minors, or glorifying serious harmful conduct.\n"
            "- Explicit sexual detail that is gratuitous, eroticized, or intended "
            "to arouse should be blocked even inside a testimony. Non-gratuitous "
            "description necessary to explain abuse or recovery may be allowed.\n"
        )

    if normalized == prayer_context:
        return (
            "PRAYER-SPECIFIC RULES:\n"
            "- Prayer requests may honestly discuss sexuality, sexual abuse, "
            "pornography addiction, suicidal thoughts, violence, trauma, or "
            "other painful subjects when asking for prayer, healing, support, "
            "repentance, or pastoral care.\n"
            "- Such support-seeking discussion should not be blocked merely "
            "because a sensitive topic appears.\n"
            "- However, gratuitous sexualized or flirtatious wording is not "
            "protected merely because the field is a Prayer caption.\n"
            "- A standalone caption such as 'sexy' has no meaningful prayer, "
            "pastoral, educational, clinical, or testimony context and should "
            "be BLOCKED with reason_code sexual.\n"
            "- Sexual solicitation, sexting requests, requests for nude images, "
            "explicit erotic material, and sexualization or exploitation of "
            "minors must be blocked.\n"
        )

    if normalized == journey_context:
        return (
            "JOURNEY-SPECIFIC RULES:\n"
            "- Journey is a short visual social-story format where users may "
            "place one or multiple text layers over an image or video.\n"
            "- Treat all supplied text layers as parts of one published social post.\n"
            "- Text may be short, expressive, poetic, devotional, reflective, "
            "or conversational.\n"
            "- Do NOT block normal prayer, Scripture discussion, testimony, "
            "personal struggle, grief, recovery, repentance, or respectful "
            "discussion of sensitive subjects merely because sensitive words appear.\n"
            "- BLOCK direct personal attacks, bullying, humiliation, threats, "
            "hate, harmful instructions, sexual solicitation, explicit erotic "
            "content, or gratuitous sexualization.\n"
            "- A standalone or nearly standalone sexualized expression such as "
            "'sexy' or an equivalent expression in another language should normally "
            "be blocked when it is being used as sexualized social content rather "
            "than legitimate educational, pastoral, clinical, safety, or testimony discussion.\n"
            "- If harmful meaning is distributed across multiple text layers, "
            "evaluate the combined meaning rather than treating each visual text "
            "box as unrelated.\n"
            "- Quoted threats, descriptions of past abuse, past suicidal thoughts, "
            "or traumatic experiences may be allowed when the author is clearly "
            "recounting, seeking help, reflecting, or describing recovery rather "
            "than endorsing the harmful act.\n"
        )

    if normalized == profile_context:
        return (
            "PROFILE-TEXT-SPECIFIC RULES:\n"
            "- This text is intended for a user's public or potentially public "
            "profile biography or vision statement.\n"
            "- Allow normal identity descriptions, faith statements, ministry "
            "vision, vocation, personal goals, life history, recovery, testimony, "
            "grief, trauma, and respectful discussion of sensitive subjects.\n"
            "- Do not block content merely because it mentions abuse, addiction, "
            "suicidal thoughts, sexuality, violence, or other difficult experiences "
            "when the user is describing their history, recovery, beliefs, support, "
            "education, or personal journey.\n"
            "- Block direct harassment, bullying, humiliation, targeted threats, "
            "hate promotion, harmful instructions, sexual solicitation, explicit "
            "erotic profile content, exploitation, scams, and other content that "
            "would make the profile itself unsafe for other users.\n"
            "- A direct invitation for sexual activity or sexualized solicitation "
            "should be blocked even when phrased as a biography or personal status.\n"
            "- Evaluate the user's actual intent and context rather than relying "
            "only on individual sensitive words.\n"
        )

    if normalized == group_message_context:
        return (
            "GROUP-MESSAGE-SPECIFIC RULES:\n"
            "- This text is a conversational message shared with multiple members "
            "inside a TownLIT group chat.\n"
            "- Group conversations are naturally more informal and interactive than "
            "public profile text or standalone social posts, so do not over-moderate "
            "ordinary conversation, disagreement, humor, frustration, or emotionally "
            "expressive language.\n"
            "- Allow normal discussion, respectful disagreement, criticism of ideas, "
            "faith discussion, prayer requests, pastoral support, personal struggles, "
            "recovery stories, testimony, education, and discussion of sensitive topics.\n"
            "- Do NOT block merely because a message mentions abuse, suicide, self-harm, "
            "sexuality, pornography, violence, addiction, hatred, crime, or threats when "
            "the user is reporting, quoting, condemning, discussing, or seeking help "
            "about those subjects.\n"
            "- Distinguish a threat made by the sender from a threat being quoted or "
            "reported. For example, reporting that someone said 'I will kill you' is "
            "not itself a threat by the current sender.\n"
            "- Distinguish support-seeking discussion of suicidal thoughts or self-harm "
            "from encouragement, instructions, or pressure to harm oneself.\n"
            "- Mild profanity, irritation, sarcasm, or non-targeted frustration should "
            "not be blocked automatically.\n"
            "- Ordinary interpersonal disagreement should not be classified as bullying "
            "or harassment merely because the tone is negative or critical.\n"
            "- BLOCK direct degrading personal attacks, sustained or severe targeted "
            "harassment, bullying, humiliation, intimidation, credible threats, hate "
            "promotion, or dehumanization of protected groups.\n"
            "- BLOCK requests for nude images, sexting, sexual activity, grooming, "
            "sexual exploitation, explicit erotic material intended to arouse, and "
            "sexualization or exploitation of minors.\n"
            "- BLOCK encouragement or actionable instructions for self-harm, serious "
            "violence, dangerous wrongdoing, or violent criminal activity.\n"
            "- BLOCK clear scams or materially abusive spam.\n"
            "- A sexual word by itself is not enough to block a conversational message "
            "when the surrounding context is legitimate, but direct sexual solicitation "
            "or gratuitous sexualization should still be blocked.\n"
            "- Evaluate the sender's actual communicative intent and the complete "
            "message context rather than relying on isolated trigger words.\n"
        )
        
    return (
        "GENERAL SOCIAL-CONTENT RULES:\n"
        "- Evaluate sexual language by meaning, not by one isolated keyword.\n"
        "- Neutral educational, clinical, biblical, pastoral, abuse-recovery, "
        "or safety discussion may be allowed.\n"
        "- Gratuitous sexualized language used to sexualize a person or body "
        "should be blocked when there is no legitimate contextual purpose.\n"
        "- A standalone or nearly standalone expression such as 'sexy' should "
        "normally be blocked as sexual content unless surrounding context clearly "
        "shows a legitimate educational, clinical, pastoral, or testimony use.\n"
        "- Sexual solicitation, sexting requests, requests for nude images, "
        "explicit erotic descriptions, and sexual exploitation must be blocked.\n"
    )


def _build_messages(
    *,
    text: str,
    context: str,
    active_categories: list[str],
    local_signals: list[str],
) -> list[dict]:
    """
    Build contextual safety messages.
    """

    system_prompt = (
        "You are TownLIT's multilingual community safety adjudicator.\n"
        "TownLIT is a Christian social application with a respectful "
        "community standard.\n\n"

        "Evaluate the user's actual meaning, intent, target, and context.\n"
        "The text may be written in any language or mixed languages.\n"
        "Do not make a decision from isolated keywords when surrounding "
        "context changes their meaning.\n\n"

        "BLOCK content that meaningfully contains any of these:\n"
        "- Severe obscene or vulgar profanity used as abuse\n"
        "- Direct degrading insults or personal attacks\n"
        "- Bullying, humiliation, or targeted abusive language\n"
        "- Threats of violence or intimidation\n"
        "- Hate or dehumanization toward protected groups\n"
        "- Explicit sexual content intended to arouse or sexualize\n"
        "- Gratuitous sexualized language directed at a person or body\n"
        "- Requests for nude images, sexting, or sexual activity\n"
        "- Any actual sexualization, grooming, or sexual exploitation of minors\n"
        "- Encouragement or instructions for self-harm\n"
        "- Promotion or instructions for serious violence\n"
        "- Harmful criminal or dangerous instructions\n"
        "- Clear scams or abusive spam\n\n"

        "Do NOT block merely because content:\n"
        "- Politely disagrees or criticizes an idea\n"
        "- Discusses sin, sexuality, addiction, or pornography non-explicitly\n"
        "- Describes past sexual abuse or trauma\n"
        "- Describes past violence, hatred, addiction, or self-harm\n"
        "- Asks for prayer, support, pastoral care, or help\n"
        "- Gives a testimony about recovery or past harmful behavior\n"
        "- Quotes offensive language to explain an event without endorsing it\n"
        "- Discusses biblical violence or crucifixion in normal context\n\n"

        "Profanity rules:\n"
        "- Mild frustration without targeting someone is not automatically blocked\n"
        "- Severe vulgar profanity aimed at a person should be blocked\n"
        "- Quoted, educational, pastoral, or testimony context must be judged "
        "by meaning rather than isolated words\n\n"

        "Sexual-content rules:\n"
        "- Be more sensitive to sexualized social language than to ordinary "
        "neutral conversation.\n"
        "- Words such as 'sexy', 'sex', 'sexual', 'nude', 'sexting', or "
        "pornography-related terms are SIGNALS, not automatic proof by themselves.\n"
        "- Clinical, educational, biblical, pastoral, testimony, abuse-recovery, "
        "or safety discussion is not automatically blocked.\n"
        "- A standalone or gratuitous use of 'sexy' that sexualizes a person, "
        "body, image, or social post should be blocked with reason_code sexual.\n"
        "- Explicit erotic descriptions intended to arouse should be blocked "
        "with reason_code sexual_explicit.\n"
        "- Requests for nude images, sexting, or sexual activity should be blocked "
        "with reason_code sexual_solicitation.\n"
        "- Actual sexualization, grooming, exploitation, or sexual solicitation "
        "involving minors must be blocked with reason_code sexual_minors.\n"
        "- Reporting or describing sexual abuse of a minor in a non-erotic "
        "victim-survivor, safety, pastoral, educational, or testimony context "
        "is not itself sexualization of a minor.\n\n"

        + _context_guidance(
            context
        )
        + "\n"

        "Use ONLY one of these reason_code values:\n"
        "- safe\n"
        "- profanity\n"
        "- abusive_language\n"
        "- personal_attack\n"
        "- bullying\n"
        "- harassment\n"
        "- harassment_threatening\n"
        "- hate\n"
        "- hate_threatening\n"
        "- sexual\n"
        "- sexual_explicit\n"
        "- sexual_solicitation\n"
        "- sexual_minors\n"
        "- self_harm\n"
        "- self_harm_intent\n"
        "- self_harm_instructions\n"
        "- violence\n"
        "- violence_graphic\n"
        "- illicit\n"
        "- illicit_violent\n"
        "- spam\n"
        "- scam\n"
        "- other_policy_violation\n\n"

        "Return valid JSON only.\n"
        "Do not include markdown or explanations.\n\n"

        "Required JSON format:\n"
        "{\n"
        '  "decision": "allow | block",\n'
        '  "risk_level": "low | medium | high | critical",\n'
        '  "reason_code": "one allowed reason code"\n'
        "}"
    )

    category_text = (
        ", ".join(
            active_categories
        )
        if active_categories
        else "none"
    )

    local_text = (
        ", ".join(
            local_signals
        )
        if local_signals
        else "none"
    )

    user_prompt = (
        f"CONTENT CONTEXT:\n{context}\n\n"
        f"MODERATION SIGNALS:\n{category_text}\n\n"
        f"LOCAL SIGNALS:\n{local_text}\n\n"
        "USER TEXT:\n"
        f"{text}"
    )

    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]


def _extract_content(
    response,
) -> str:
    """
    Extract assistant JSON content.
    """

    try:
        return str(
            response.choices[
                0
            ].message.content
            or ""
        ).strip()

    except Exception:
        return ""


def _normalize_reason_code(
    value: str,
) -> str:
    """
    Canonicalize one reason code.
    """

    reason = str(
        value
        or ""
    ).strip().lower()

    reason = re.sub(
        r"[^a-z0-9]+",
        "_",
        reason,
    ).strip(
        "_"
    )

    if reason in _ALLOWED_REASON_CODES:
        return reason

    alias = _REASON_ALIASES.get(
        reason
    )

    if alias:
        return alias

    return "other_policy_violation"


def _parse_adjudication(
    raw_content: str,
) -> TextSafetyAdjudication:
    """
    Validate adjudication JSON.
    """

    if not raw_content:
        raise RuntimeError(
            "Safety adjudication returned empty content."
        )

    try:
        payload = json.loads(
            raw_content
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Safety adjudication returned invalid JSON."
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Safety adjudication returned an invalid payload."
        )

    payload[
        "reason_code"
    ] = _normalize_reason_code(
        payload.get(
            "reason_code",
            "",
        )
    )

    try:
        return TextSafetyAdjudication.model_validate(
            payload
        )

    except ValidationError as exc:
        raise RuntimeError(
            "Safety adjudication returned an invalid schema."
        ) from exc


def adjudicate_text(
    *,
    text: str,
    context: str,
    active_categories: list[str],
    local_signals: list[str],
) -> dict:
    """
    Resolve TownLIT contextual safety.
    """

    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is missing."
        )

    model = (
        settings.CONTENT_SAFETY_ADJUDICATION_MODEL
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

    response = client.chat.completions.create(
        model=model,
        messages=_build_messages(
            text=text,
            context=context,
            active_categories=active_categories,
            local_signals=local_signals,
        ),
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
            "Invalid safety adjudication decision."
        )

    if risk_level not in {
        SafetyRiskLevel.LOW,
        SafetyRiskLevel.MEDIUM,
        SafetyRiskLevel.HIGH,
        SafetyRiskLevel.CRITICAL,
    }:
        raise RuntimeError(
            "Invalid safety adjudication risk level."
        )

    return {
        "decision": decision,
        "risk_level": risk_level,
        "reason_code": _normalize_reason_code(
            parsed.reason_code
        ),
        "model": model,
    }
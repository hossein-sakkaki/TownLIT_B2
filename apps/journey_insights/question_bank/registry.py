# apps/journey_insights/question_bank/registry.py

from __future__ import annotations

from apps.journey_insights.question_bank.compassion import QUESTIONS as COMPASSION
from apps.journey_insights.question_bank.connection import QUESTIONS as CONNECTION
from apps.journey_insights.question_bank.courage import QUESTIONS as COURAGE
from apps.journey_insights.question_bank.faith import QUESTIONS as FAITH
from apps.journey_insights.question_bank.gratitude import QUESTIONS as GRATITUDE
from apps.journey_insights.question_bank.growth import QUESTIONS as GROWTH
from apps.journey_insights.question_bank.hope import QUESTIONS as HOPE
from apps.journey_insights.question_bank.peace import QUESTIONS as PEACE
from apps.journey_insights.question_bank.purpose import QUESTIONS as PURPOSE
from apps.journey_insights.question_bank.resilience import QUESTIONS as RESILIENCE
from apps.journey_insights.question_bank.rest import QUESTIONS as REST
from apps.journey_insights.question_bank.self_awareness import QUESTIONS as SELF_AWARENESS


QUESTION_BANK = [
    *GRATITUDE,
    *PEACE,
    *HOPE,
    *FAITH,
    *CONNECTION,
    *PURPOSE,
    *COURAGE,
    *COMPASSION,
    *SELF_AWARENESS,
    *RESILIENCE,
    *REST,
    *GROWTH,
]


def validate_question_bank() -> None:
    question_codes: set[str] = set()

    for definition in QUESTION_BANK:
        code = definition["code"]

        if code in question_codes:
            raise ValueError(f"Duplicate reflection question code: {code}")

        question_codes.add(code)

        choices = definition.get("choices") or []

        if len(choices) < 2:
            raise ValueError(f"Question '{code}' must have at least two choices.")

        choice_codes: set[str] = set()

        for item in choices:
            choice_code = item["code"]

            if choice_code in choice_codes:
                raise ValueError(
                    f"Duplicate choice code '{choice_code}' in question '{code}'."
                )

            choice_codes.add(choice_code)
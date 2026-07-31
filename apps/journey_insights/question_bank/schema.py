# apps/journey_insights/question_bank/schema.py

from __future__ import annotations

from typing import Any


def choice(
    *,
    code: str,
    label: str,
    base_score: float,
    weights: dict[str, float],
    metadata: dict[str, Any] | None = None,
) -> dict:
    return {
        "code": code,
        "label": label,
        "base_score": base_score,
        "weights": weights,
        "metadata": metadata or {},
    }


def question(
    *,
    code: str,
    prompt: str,
    dimension: str,
    choices: list[dict],
    secondary_dimensions: list[str] | None = None,
    difficulty: int = 1,
    sensitivity: int = 1,
    selection_weight: float = 1.0,
    minimum_journey_entries: int = 1,
    minimum_active_days_in_month: int = 1,
    allow_for_new_users: bool = True,
    is_brand_core: bool = False,
    version: int = 1,
    metadata: dict[str, Any] | None = None,
) -> dict:
    return {
        "code": code,
        "prompt": prompt,
        "dimension": dimension,
        "secondary_dimensions": secondary_dimensions or [],
        "choices": choices,
        "difficulty": difficulty,
        "sensitivity": sensitivity,
        "selection_weight": selection_weight,
        "minimum_journey_entries": minimum_journey_entries,
        "minimum_active_days_in_month": minimum_active_days_in_month,
        "allow_for_new_users": allow_for_new_users,
        "is_brand_core": is_brand_core,
        "version": version,
        "metadata": metadata or {},
    }
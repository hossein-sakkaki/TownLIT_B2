# apps/journey_insights/models/questions.py

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.journey_insights.constants import (
    ReflectionDimension,
    ReflectionQuestionKind,
    ReflectionQuestionStatus,
)


class ReflectionQuestion(models.Model):
    """
    Canonical English reflection question.

    Translation is handled by TownLIT translation tools.
    """

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    code = models.CharField(max_length=100, unique=True)
    prompt = models.TextField()

    kind = models.CharField(
        max_length=32,
        choices=ReflectionQuestionKind.choices,
        default=ReflectionQuestionKind.SINGLE_CHOICE,
        db_index=True,
    )

    primary_dimension = models.CharField(
        max_length=32,
        choices=ReflectionDimension.choices,
        db_index=True,
    )

    secondary_dimensions = models.JSONField(default=list, blank=True)

    status = models.CharField(
        max_length=16,
        choices=ReflectionQuestionStatus.choices,
        default=ReflectionQuestionStatus.DRAFT,
        db_index=True,
    )

    difficulty = models.PositiveSmallIntegerField(default=1)
    sensitivity = models.PositiveSmallIntegerField(default=1)

    selection_weight = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=1,
    )

    minimum_journey_entries = models.PositiveSmallIntegerField(default=1)
    minimum_active_days_in_month = models.PositiveSmallIntegerField(default=1)

    allow_for_new_users = models.BooleanField(default=True)
    is_brand_core = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)

    version = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        if not self.prompt or not self.prompt.strip():
            raise ValidationError(
                {"prompt": "Question prompt is required."}
            )

        if self.difficulty < 1 or self.difficulty > 5:
            raise ValidationError(
                {"difficulty": "Difficulty must be between 1 and 5."}
            )

        if self.sensitivity < 1 or self.sensitivity > 5:
            raise ValidationError(
                {"sensitivity": "Sensitivity must be between 1 and 5."}
            )

        if not isinstance(self.secondary_dimensions, list):
            raise ValidationError(
                {
                    "secondary_dimensions": (
                        "Secondary dimensions must be a list."
                    ),
                }
            )

        valid_dimensions = {
            value
            for value, _ in ReflectionDimension.choices
        }

        invalid_dimensions = {
            value
            for value in self.secondary_dimensions
            if value not in valid_dimensions
        }

        if invalid_dimensions:
            raise ValidationError(
                {
                    "secondary_dimensions": (
                        f"Invalid dimensions: {sorted(invalid_dimensions)}"
                    ),
                }
            )

        if self.primary_dimension in self.secondary_dimensions:
            raise ValidationError(
                {
                    "secondary_dimensions": (
                        "Primary dimension cannot also be secondary."
                    ),
                }
            )

    def __str__(self):
        return f"{self.code} · {self.primary_dimension}"

    class Meta:
        verbose_name = "Reflection Question"
        verbose_name_plural = "Reflection Questions"
        ordering = ("primary_dimension", "code")

        indexes = [
            models.Index(
                fields=("status", "is_active", "primary_dimension"),
                name="reflection_question_active_idx",
            ),
            models.Index(
                fields=("kind", "difficulty", "sensitivity"),
                name="reflection_question_kind_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=Q(difficulty__gte=1) & Q(difficulty__lte=5),
                name="reflection_question_difficulty_range",
            ),
            models.CheckConstraint(
                check=Q(sensitivity__gte=1) & Q(sensitivity__lte=5),
                name="reflection_question_sensitivity_range",
            ),
            models.CheckConstraint(
                check=Q(selection_weight__gt=0),
                name="reflection_question_weight_positive",
            ),
        ]


class ReflectionChoice(models.Model):
    """
    Canonical English answer choice.

    Client never receives scoring metadata.
    """

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    question = models.ForeignKey(
        ReflectionQuestion,
        on_delete=models.CASCADE,
        related_name="choices",
    )

    code = models.CharField(max_length=64)
    label = models.CharField(max_length=500)
    order = models.PositiveSmallIntegerField(default=0)

    is_active = models.BooleanField(default=True, db_index=True)

    base_score = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=0,
    )

    dimension_weights = models.JSONField(default=dict, blank=True)
    scoring_profile = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        if not self.label or not self.label.strip():
            raise ValidationError(
                {"label": "Choice label is required."}
            )

        if not isinstance(self.dimension_weights, dict):
            raise ValidationError(
                {
                    "dimension_weights": (
                        "Dimension weights must be an object."
                    ),
                }
            )

        valid_dimensions = {
            value
            for value, _ in ReflectionDimension.choices
        }

        invalid_dimensions = {
            key
            for key in self.dimension_weights.keys()
            if key not in valid_dimensions
        }

        if invalid_dimensions:
            raise ValidationError(
                {
                    "dimension_weights": (
                        f"Invalid dimensions: {sorted(invalid_dimensions)}"
                    ),
                }
            )

        for dimension, weight in self.dimension_weights.items():
            try:
                numeric_weight = float(weight)
            except (TypeError, ValueError):
                raise ValidationError(
                    {
                        "dimension_weights": (
                            f"Weight for '{dimension}' must be numeric."
                        ),
                    }
                )

            if numeric_weight < -5 or numeric_weight > 5:
                raise ValidationError(
                    {
                        "dimension_weights": (
                            f"Weight for '{dimension}' must be between -5 and 5."
                        ),
                    }
                )

    def __str__(self):
        return f"{self.question.code} · {self.code}"

    class Meta:
        verbose_name = "Reflection Choice"
        verbose_name_plural = "Reflection Choices"
        ordering = ("question_id", "order", "id")

        constraints = [
            models.UniqueConstraint(
                fields=("question", "code"),
                name="reflection_unique_question_choice_code",
            ),
            models.UniqueConstraint(
                fields=("question", "order"),
                name="reflection_unique_question_choice_order",
            ),
        ]

        indexes = [
            models.Index(
                fields=("question", "is_active", "order"),
                name="reflection_choice_active_idx",
            ),
        ]
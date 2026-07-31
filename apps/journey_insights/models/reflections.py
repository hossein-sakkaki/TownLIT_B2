# apps/journey_insights/models/reflections.py

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.journey_insights.constants import (
    QUESTION_SELECTION_VERSION,
    REFLECTION_SCORING_VERSION,
    ReflectionAnswerStatus,
    ReflectionSessionStatus,
    ReflectionSourceKind,
)
from apps.journey_insights.models.questions import (
    ReflectionChoice,
    ReflectionQuestion,
)


class ReflectionSession(models.Model):
    """
    One set of reflection questions presented to one user.
    """

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reflection_sessions",
    )

    source_kind = models.CharField(
        max_length=24,
        choices=ReflectionSourceKind.choices,
        default=ReflectionSourceKind.JOURNEY,
        db_index=True,
    )

    source_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reflection_sessions",
    )

    source_object_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    source_object = GenericForeignKey(
        "source_content_type",
        "source_object_id",
    )

    status = models.CharField(
        max_length=16,
        choices=ReflectionSessionStatus.choices,
        default=ReflectionSessionStatus.OPEN,
        db_index=True,
    )

    selection_version = models.CharField(
        max_length=100,
        default=QUESTION_SELECTION_VERSION,
    )

    scoring_version = models.CharField(
        max_length=100,
        default=REFLECTION_SCORING_VERSION,
    )

    question_count = models.PositiveSmallIntegerField(default=0)
    answered_count = models.PositiveSmallIntegerField(default=0)

    score_total = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )

    dimension_scores = models.JSONField(default=dict, blank=True)
    selection_context = models.JSONField(default=dict, blank=True)

    opened_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    expires_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        has_ct = self.source_content_type_id is not None
        has_object_id = self.source_object_id is not None

        if has_ct != has_object_id:
            raise ValidationError(
                "Source content type and object ID must be provided together."
            )

        if self.expires_at <= self.opened_at:
            raise ValidationError(
                {
                    "expires_at": (
                        "Session expiry must be after opening time."
                    ),
                }
            )

    @property
    def is_open(self):
        return (
            self.status == ReflectionSessionStatus.OPEN
            and self.expires_at > timezone.now()
        )

    def __str__(self):
        return f"Reflection Session {self.public_id} · {self.user_id}"

    class Meta:
        verbose_name = "Reflection Session"
        verbose_name_plural = "Reflection Sessions"
        ordering = ("-opened_at", "-id")

        indexes = [
            models.Index(
                fields=("user", "status", "-opened_at"),
                name="reflection_session_user_idx",
            ),
            models.Index(
                fields=(
                    "source_kind",
                    "source_content_type",
                    "source_object_id",
                ),
                name="reflection_session_source_idx",
            ),
            models.Index(
                fields=("status", "expires_at"),
                name="reflection_session_expiry_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=Q(question_count__gte=0),
                name="reflection_session_question_count_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(answered_count__gte=0),
                name="reflection_session_answer_count_nonnegative",
            ),
        ]


class ReflectionSessionQuestion(models.Model):
    """
    Immutable question assignment snapshot.
    """

    id = models.BigAutoField(primary_key=True)

    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    session = models.ForeignKey(
        ReflectionSession,
        on_delete=models.CASCADE,
        related_name="session_questions",
    )

    question = models.ForeignKey(
        ReflectionQuestion,
        on_delete=models.PROTECT,
        related_name="session_assignments",
    )

    position = models.PositiveSmallIntegerField()

    prompt_snapshot = models.TextField()
    kind_snapshot = models.CharField(max_length=32)
    primary_dimension_snapshot = models.CharField(max_length=32)
    choice_snapshot = models.JSONField(default=list)

    selection_score = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )

    selection_reason = models.JSONField(default=dict, blank=True)

    presented_at = models.DateTimeField(default=timezone.now)
    answered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return (
            f"Reflection Assignment {self.public_id} · "
            f"{self.session_id} · {self.position} · "
            f"{self.question.code}"
        )

    class Meta:
        verbose_name = "Reflection Session Question"
        verbose_name_plural = "Reflection Session Questions"
        ordering = ("position", "id")

        constraints = [
            models.UniqueConstraint(
                fields=("session", "question"),
                name="reflection_unique_session_question",
            ),
            models.UniqueConstraint(
                fields=("session", "position"),
                name="reflection_unique_session_position",
            ),
        ]


class ReflectionAnswer(models.Model):
    """
    Submitted answer with immutable scoring snapshot.
    """

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    session_question = models.OneToOneField(
        ReflectionSessionQuestion,
        on_delete=models.CASCADE,
        related_name="answer",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reflection_answers",
    )

    status = models.CharField(
        max_length=16,
        choices=ReflectionAnswerStatus.choices,
        default=ReflectionAnswerStatus.SUBMITTED,
        db_index=True,
    )

    selected_choices = models.ManyToManyField(
        ReflectionChoice,
        blank=True,
        related_name="reflection_answers",
    )

    selected_choice_codes = models.JSONField(default=list)
    response_value = models.JSONField(default=dict, blank=True)

    raw_score = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
    )

    normalized_score = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        default=0,
    )

    dimension_scores = models.JSONField(default=dict, blank=True)
    scoring_snapshot = models.JSONField(default=dict, blank=True)

    submitted_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        if (
            self.session_question_id
            and self.user_id
            and self.session_question.session.user_id != self.user_id
        ):
            raise ValidationError(
                "Answer user does not own this session."
            )

    def __str__(self):
        return f"Reflection Answer {self.public_id}"

    class Meta:
        verbose_name = "Reflection Answer"
        verbose_name_plural = "Reflection Answers"
        ordering = ("-submitted_at", "-id")

        indexes = [
            models.Index(
                fields=("user", "-submitted_at"),
                name="refl_ans_user_time_idx",
            ),
            models.Index(
                fields=("status", "-submitted_at"),
                name="refl_ans_status_idx",
            ),
        ]


class ReflectionQuestionExposure(models.Model):
    """
    Persistent user/question exposure ledger.

    Questions are not repeated until the active bank is exhausted.
    """

    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reflection_question_exposures",
    )

    question = models.ForeignKey(
        ReflectionQuestion,
        on_delete=models.CASCADE,
        related_name="user_exposures",
    )

    exposure_cycle = models.PositiveIntegerField(
        default=1,
        db_index=True,
    )

    times_presented = models.PositiveIntegerField(default=1)
    times_answered = models.PositiveIntegerField(default=0)

    first_presented_at = models.DateTimeField(default=timezone.now)
    last_presented_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    last_answered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.user_id} · {self.question.code} · "
            f"cycle {self.exposure_cycle}"
        )

    class Meta:
        verbose_name = "Reflection Question Exposure"
        verbose_name_plural = "Reflection Question Exposures"

        constraints = [
            models.UniqueConstraint(
                fields=("user", "question"),
                name="refl_unique_user_question",
            ),
        ]

        indexes = [
            models.Index(
                fields=("user", "exposure_cycle", "last_presented_at"),
                name="refl_exp_cycle_idx",
            ),
            models.Index(
                fields=("user", "question", "times_presented"),
                name="refl_exp_question_idx",
            ),
        ]
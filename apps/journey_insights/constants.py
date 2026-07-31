# apps/journey_insights/constants.py

from django.db import models


class ReflectionQuestionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    RETIRED = "retired", "Retired"


class ReflectionQuestionKind(models.TextChoices):
    SINGLE_CHOICE = "single_choice", "Single Choice"
    MULTIPLE_CHOICE = "multiple_choice", "Multiple Choice"
    SCALE = "scale", "Scale"


class ReflectionDimension(models.TextChoices):
    GRATITUDE = "gratitude", "Gratitude"
    PEACE = "peace", "Peace"
    HOPE = "hope", "Hope"
    FAITH = "faith", "Faith"
    CONNECTION = "connection", "Connection"
    PURPOSE = "purpose", "Purpose"
    COURAGE = "courage", "Courage"
    COMPASSION = "compassion", "Compassion"
    SELF_AWARENESS = "self_awareness", "Self Awareness"
    RESILIENCE = "resilience", "Resilience"
    REST = "rest", "Rest"
    GROWTH = "growth", "Growth"


class ReflectionSourceKind(models.TextChoices):
    JOURNEY = "journey", "Journey"
    MOMENT = "moment", "Moment"
    TESTIMONY = "testimony", "Testimony"
    PRAYER = "prayer", "Prayer"
    SYSTEM = "system", "System"


class ReflectionSessionStatus(models.TextChoices):
    OPEN = "open", "Open"
    COMPLETED = "completed", "Completed"
    EXPIRED = "expired", "Expired"
    CANCELLED = "cancelled", "Cancelled"


class ReflectionAnswerStatus(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    INVALIDATED = "invalidated", "Invalidated"


class MonthlyInsightStatus(models.TextChoices):
    BUILDING = "building", "Building"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class InsightTrend(models.TextChoices):
    UP = "up", "Up"
    STABLE = "stable", "Stable"
    DOWN = "down", "Down"
    INSUFFICIENT = "insufficient", "Insufficient Data"


REFLECTION_QUESTION_COOLDOWN_DAYS = 30
REFLECTION_SESSION_EXPIRY_HOURS = 48
REFLECTION_DEFAULT_QUESTIONS_PER_SESSION = 3
REFLECTION_MAX_QUESTIONS_PER_SESSION = 5

MONTHLY_INSIGHT_MIN_ANSWER_COUNT = 3
MONTHLY_INSIGHT_MIN_ACTIVE_DAYS = 2

SCORE_SCALE_MIN = 0
SCORE_SCALE_MAX = 100

QUESTION_SELECTION_VERSION = "journey-reflection-selection-v1"
REFLECTION_SCORING_VERSION = "journey-reflection-scoring-v1"
MONTHLY_INSIGHT_VERSION = "journey-monthly-insight-v1"


class DailyReflectionPromptStatus(
    models.TextChoices,
):
    PENDING = (
        "pending",
        "Pending",
    )
    DEFERRED = (
        "deferred",
        "Deferred",
    )
    SKIPPED = (
        "skipped",
        "Skipped for today",
    )
    ANSWERED = (
        "answered",
        "Answered",
    )
    EXPIRED = (
        "expired",
        "Expired",
    )
    
class DailyReflectionPromptDecision(
    models.TextChoices,
):
    ANSWER_NOW = (
        "answer_now",
        "Answer now",
    )
    ASK_LATER = (
        "ask_later",
        "Ask me later",
    )
    SKIP_TODAY = (
        "skip_today",
        "Not today",
    )
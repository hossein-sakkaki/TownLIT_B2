# apps/journey_insights/admin.py

from django.contrib import admin

from apps.journey_insights.models import (
    MonthlyInsightDimension,
    MonthlyInsightReport,
    ReflectionAnswer,
    ReflectionChoice,
    ReflectionQuestion,
    ReflectionQuestionExposure,
    ReflectionSession,
    ReflectionSessionQuestion,
)


class ReflectionChoiceInline(admin.TabularInline):
    model = ReflectionChoice
    extra = 0


@admin.register(ReflectionQuestion)
class ReflectionQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "primary_dimension",
        "kind",
        "status",
        "difficulty",
        "sensitivity",
        "selection_weight",
        "is_active",
    )
    list_filter = (
        "status",
        "kind",
        "primary_dimension",
        "difficulty",
        "sensitivity",
        "is_active",
    )
    search_fields = ("code", "prompt")
    inlines = [ReflectionChoiceInline]


@admin.register(ReflectionSession)
class ReflectionSessionAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "user",
        "source_kind",
        "status",
        "question_count",
        "answered_count",
        "opened_at",
        "completed_at",
    )
    list_filter = ("source_kind", "status")
    search_fields = ("public_id", "user__email", "user__username")


@admin.register(ReflectionSessionQuestion)
class ReflectionSessionQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "session",
        "position",
        "question",
        "presented_at",
        "answered_at",
    )


@admin.register(ReflectionAnswer)
class ReflectionAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "user",
        "normalized_score",
        "status",
        "submitted_at",
    )
    list_filter = ("status",)
    search_fields = ("public_id", "user__email", "user__username")


@admin.register(ReflectionQuestionExposure)
class ReflectionQuestionExposureAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "question",
        "exposure_cycle",
        "times_presented",
        "times_answered",
        "last_presented_at",
    )
    list_filter = ("exposure_cycle",)
    search_fields = ("user__email", "user__username", "question__code")


class MonthlyInsightDimensionInline(admin.TabularInline):
    model = MonthlyInsightDimension
    extra = 0
    readonly_fields = (
        "dimension",
        "score",
        "previous_score",
        "trend",
        "confidence",
        "sample_count",
    )


@admin.register(MonthlyInsightReport)
class MonthlyInsightReportAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "year",
        "month",
        "status",
        "is_sufficient",
        "overall_score",
        "overall_trend",
        "generated_at",
    )
    list_filter = (
        "status",
        "is_sufficient",
        "overall_trend",
        "year",
        "month",
    )
    search_fields = ("user__email", "user__username", "public_id")
    inlines = [MonthlyInsightDimensionInline]
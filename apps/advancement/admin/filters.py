# apps/advancement/admin/filters.py

from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q


class OpportunityPipelineFilter(admin.SimpleListFilter):
    """Quick pipeline state filter."""
    title = "pipeline group"
    parameter_name = "pipeline_group"

    def lookups(self, request, model_admin):
        return (
            ("active_pipeline", "Active Pipeline"),
            ("approved", "Approved"),
            ("declined_closed", "Declined / Closed"),
        )

    def queryset(self, request, queryset):
        if self.value() == "active_pipeline":
            return queryset.filter(stage__in=["PROSPECT", "LOI", "SUBMITTED", "UNDER_REVIEW"])
        if self.value() == "approved":
            return queryset.filter(stage="APPROVED")
        if self.value() == "declined_closed":
            return queryset.filter(stage__in=["DECLINED", "CLOSED"])
        return queryset


class OpportunityDeadlineStatusFilter(admin.SimpleListFilter):
    """Show overdue/upcoming opportunities."""
    title = "deadline status"
    parameter_name = "deadline_status"

    def lookups(self, request, model_admin):
        return (
            ("overdue", "Overdue"),
            ("next_30_days", "Next 30 days"),
            ("no_deadline", "No deadline"),
        )

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == "overdue":
            return queryset.filter(deadline__lt=today).exclude(stage__in=["APPROVED", "DECLINED", "CLOSED"])
        if self.value() == "next_30_days":
            return queryset.filter(deadline__gte=today, deadline__lte=today + timedelta(days=30))
        if self.value() == "no_deadline":
            return queryset.filter(deadline__isnull=True)
        return queryset


class InteractionFollowUpFilter(admin.SimpleListFilter):
    """Highlight follow-up work."""
    title = "follow-up"
    parameter_name = "followup_status"

    def lookups(self, request, model_admin):
        return (
            ("overdue", "Overdue next action"),
            ("today", "Due today"),
            ("open", "Open / Waiting"),
        )

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == "overdue":
            return queryset.filter(next_action_date__lt=today, status__in=["OPEN", "WAITING"])
        if self.value() == "today":
            return queryset.filter(next_action_date=today, status__in=["OPEN", "WAITING"])
        if self.value() == "open":
            return queryset.filter(status__in=["OPEN", "WAITING"])
        return queryset


class HighStrategicScoreFilter(admin.SimpleListFilter):
    """Quick score threshold filter."""
    title = "strategic score"
    parameter_name = "score_band"

    def lookups(self, request, model_admin):
        return (
            ("high", "High (>= 20)"),
            ("medium", "Medium (12-19)"),
            ("low", "Low (< 12)"),
            ("missing", "No score"),
        )

    def queryset(self, request, queryset):
        if self.value() == "high":
            return queryset.filter(
                strategic_score__mission_alignment__gte=0  # ensure relation exists
            ).extra(
                where=[
                    "(mission_alignment + funding_capacity + access_level + influence_value - effort_required) >= 20"
                ],
                tables=["advancement_strategicscore"]
            )
        if self.value() == "medium":
            return queryset.extra(
                where=[
                    "(advancement_strategicscore.mission_alignment + advancement_strategicscore.funding_capacity + advancement_strategicscore.access_level + advancement_strategicscore.influence_value - advancement_strategicscore.effort_required) BETWEEN 12 AND 19"
                ],
                tables=["advancement_strategicscore"]
            )
        if self.value() == "low":
            return queryset.extra(
                where=[
                    "(advancement_strategicscore.mission_alignment + advancement_strategicscore.funding_capacity + advancement_strategicscore.access_level + advancement_strategicscore.influence_value - advancement_strategicscore.effort_required) < 12"
                ],
                tables=["advancement_strategicscore"]
            )
        if self.value() == "missing":
            return queryset.filter(strategic_score__isnull=True)
        return queryset
# apps/advancement/services/board_snapshot.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.advancement.models import (
    Commitment,
    ExternalEntity,
    InteractionLog,
    LegalEntity,
    Opportunity,
)


@dataclass
class BoardSnapshot:
    """Structured board dashboard snapshot."""
    generated_at: Any
    as_of_date: Any

    # KPI summary
    pledged_total: Decimal
    confirmed_total: Decimal
    pipeline_value: Decimal  # planning metric (may mix currencies)
    approval_rate: float
    overdue_followups: int
    due_today_followups: int
    entity_count: int
    opp_count: int
    commitment_count: int
    active_pipeline_count: int

    # Table rows (dict-based for template/export/pdf reuse)
    stage_rows: list[dict[str, Any]]
    legal_entity_rows: list[dict[str, Any]]
    top_entity_rows: list[dict[str, Any]]
    overdue_rows: list[dict[str, Any]]
    upcoming_rows: list[dict[str, Any]]
    recent_interaction_rows: list[dict[str, Any]]


def build_board_snapshot() -> BoardSnapshot:
    """Build board-ready advancement snapshot."""
    today = timezone.localdate()
    now = timezone.now()
    next_30 = today + timedelta(days=30)

    # Commitment totals (base currency reporting)
    pledged_total = (
        Commitment.objects.filter(
            status__in=["PLEDGED", "CONDITIONAL", "CONFIRMED", "FULFILLED"]
        ).aggregate(total=Sum("base_currency_amount"))["total"]
        or Decimal("0.00")
    )

    confirmed_total = (
        Commitment.objects.filter(
            status__in=["CONFIRMED", "FULFILLED"]
        ).aggregate(total=Sum("base_currency_amount"))["total"]
        or Decimal("0.00")
    )

    # Planning metric (expected_amount may be mixed currency)
    pipeline_value = (
        Opportunity.objects.filter(
            stage__in=["PROSPECT", "LOI", "SUBMITTED", "UNDER_REVIEW"]
        ).aggregate(total=Sum("expected_amount"))["total"]
        or Decimal("0.00")
    )

    # Approval rate
    approved_count = Opportunity.objects.filter(stage="APPROVED").count()
    terminal_count = Opportunity.objects.filter(stage__in=["APPROVED", "DECLINED"]).count()
    approval_rate = round((approved_count / terminal_count) * 100, 1) if terminal_count else 0.0

    # Stage distribution
    stage_labels = dict(Opportunity.STAGE_CHOICES)
    raw_stage_counts = (
        Opportunity.objects.values("stage")
        .annotate(count=Count("id"))
        .order_by("stage")
    )
    stage_rows = [
        {
            "stage": row["stage"],
            "label": stage_labels.get(row["stage"], row["stage"]),
            "count": row["count"],
        }
        for row in raw_stage_counts
    ]

    # Totals by legal entity
    legal_entity_totals = (
        LegalEntity.objects
        .annotate(
            total_pledged=Sum(
                "opportunities__commitments__base_currency_amount",
                filter=Q(
                    opportunities__commitments__status__in=[
                        "PLEDGED",
                        "CONDITIONAL",
                        "CONFIRMED",
                        "FULFILLED",
                    ]
                ),
            ),
            total_confirmed=Sum(
                "opportunities__commitments__base_currency_amount",
                filter=Q(opportunities__commitments__status__in=["CONFIRMED", "FULFILLED"]),
            ),
        )
        .order_by("name")
    )
    legal_entity_rows = [
        {
            "name": le.name,
            "country": getattr(le, "country", ""),
            "base_currency": getattr(le, "base_currency", ""),
            "total_pledged": le.total_pledged or Decimal("0.00"),
            "total_confirmed": le.total_confirmed or Decimal("0.00"),
        }
        for le in legal_entity_totals
    ]

    # Top external entities by pledged
    top_entities = (
        ExternalEntity.objects
        .annotate(
            pledged_total=Sum(
                "opportunities__commitments__base_currency_amount",
                filter=Q(
                    opportunities__commitments__status__in=[
                        "PLEDGED",
                        "CONDITIONAL",
                        "CONFIRMED",
                        "FULFILLED",
                    ]
                ),
            ),
            confirmed_total=Sum(
                "opportunities__commitments__base_currency_amount",
                filter=Q(opportunities__commitments__status__in=["CONFIRMED", "FULFILLED"]),
            ),
            opportunity_count=Count("opportunities", distinct=True),
        )
        .filter(Q(pledged_total__isnull=False) | Q(opportunity_count__gt=0))
        .order_by("-pledged_total", "name")[:10]
    )
    top_entity_rows = [
        {
            "name": e.name,
            "entity_type": e.get_entity_type_display(),
            "country": e.country,
            "pledged_total": e.pledged_total or Decimal("0.00"),
            "confirmed_total": e.confirmed_total or Decimal("0.00"),
            "opportunity_count": e.opportunity_count or 0,
        }
        for e in top_entities
    ]

    # Overdue opportunities (active pipeline only)
    overdue_qs = (
        Opportunity.objects
        .select_related("external_entity", "legal_entity")
        .filter(
            deadline__lt=today,
            stage__in=["PROSPECT", "LOI", "SUBMITTED", "UNDER_REVIEW"],
        )
        .order_by("deadline")[:50]
    )
    overdue_rows = [
        {
            "deadline": o.deadline,
            "title": o.title,
            "external_entity": o.external_entity.name,
            "legal_entity": o.legal_entity.name if o.legal_entity_id else "",
            "stage": o.get_stage_display(),
            "currency": o.currency,
            "expected_amount": o.expected_amount,
        }
        for o in overdue_qs
    ]

    # Upcoming deadlines (next 30 days)
    upcoming_qs = (
        Opportunity.objects
        .select_related("external_entity", "legal_entity")
        .filter(
            deadline__gte=today,
            deadline__lte=next_30,
            stage__in=["PROSPECT", "LOI", "SUBMITTED", "UNDER_REVIEW"],
        )
        .order_by("deadline")[:50]
    )
    upcoming_rows = [
        {
            "deadline": o.deadline,
            "title": o.title,
            "external_entity": o.external_entity.name,
            "legal_entity": o.legal_entity.name if o.legal_entity_id else "",
            "stage": o.get_stage_display(),
            "currency": o.currency,
            "expected_amount": o.expected_amount,
        }
        for o in upcoming_qs
    ]

    # Follow-up counters
    overdue_followups = InteractionLog.objects.filter(
        status__in=["OPEN", "WAITING"],
        next_action_date__lt=today,
    ).count()

    due_today_followups = InteractionLog.objects.filter(
        status__in=["OPEN", "WAITING"],
        next_action_date=today,
    ).count()

    # Recent interactions
    recent_qs = (
        InteractionLog.objects
        .select_related("external_entity", "assigned_to")
        .order_by("-created_at")[:25]
    )
    recent_interaction_rows = [
        {
            "created_at": i.created_at,
            "external_entity": i.external_entity.name,
            "interaction_type": i.get_interaction_type_display(),
            "status": i.get_status_display(),
            "subject": i.subject or "",
            "assigned_to": str(i.assigned_to) if i.assigned_to else "",
        }
        for i in recent_qs
    ]

    return BoardSnapshot(
        generated_at=now,
        as_of_date=today,
        pledged_total=pledged_total,
        confirmed_total=confirmed_total,
        pipeline_value=pipeline_value,
        approval_rate=approval_rate,
        overdue_followups=overdue_followups,
        due_today_followups=due_today_followups,
        entity_count=ExternalEntity.objects.count(),
        opp_count=Opportunity.objects.count(),
        commitment_count=Commitment.objects.count(),
        active_pipeline_count=Opportunity.objects.filter(
            stage__in=["PROSPECT", "LOI", "SUBMITTED", "UNDER_REVIEW"]
        ).count(),
        stage_rows=stage_rows,
        legal_entity_rows=legal_entity_rows,
        top_entity_rows=top_entity_rows,
        overdue_rows=overdue_rows,
        upcoming_rows=upcoming_rows,
        recent_interaction_rows=recent_interaction_rows,
    )
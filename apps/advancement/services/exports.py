# apps/advancement/services/exports.py

from __future__ import annotations

import csv
from io import StringIO
from django.http import HttpResponse

from .board_snapshot import BoardSnapshot


def _write_section(writer: csv.writer, title: str, headers: list[str], rows: list[list]):
    """Write a titled CSV section."""
    writer.writerow([title])
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    writer.writerow([])  # spacer


def build_board_snapshot_csv_response(snapshot: BoardSnapshot) -> HttpResponse:
    """Create CSV response for board snapshot."""
    buffer = StringIO()
    writer = csv.writer(buffer)

    # Summary section
    _write_section(
        writer,
        "SUMMARY",
        ["metric", "value"],
        [
            ["generated_at", snapshot.generated_at.isoformat()],
            ["as_of_date", str(snapshot.as_of_date)],
            ["pledged_total", str(snapshot.pledged_total)],
            ["confirmed_total", str(snapshot.confirmed_total)],
            ["pipeline_value_planning_metric", str(snapshot.pipeline_value)],
            ["approval_rate_percent", str(snapshot.approval_rate)],
            ["overdue_followups", snapshot.overdue_followups],
            ["due_today_followups", snapshot.due_today_followups],
            ["entity_count", snapshot.entity_count],
            ["opportunity_count", snapshot.opp_count],
            ["commitment_count", snapshot.commitment_count],
            ["active_pipeline_count", snapshot.active_pipeline_count],
        ],
    )

    # Stage distribution
    _write_section(
        writer,
        "STAGE_DISTRIBUTION",
        ["stage_code", "stage_label", "count"],
        [
            [r["stage"], r["label"], r["count"]]
            for r in snapshot.stage_rows
        ],
    )

    # Legal entity totals
    _write_section(
        writer,
        "LEGAL_ENTITY_TOTALS",
        ["name", "country", "base_currency", "total_pledged", "total_confirmed"],
        [
            [r["name"], r["country"], r["base_currency"], r["total_pledged"], r["total_confirmed"]]
            for r in snapshot.legal_entity_rows
        ],
    )

    # Top entities
    _write_section(
        writer,
        "TOP_ENTITIES",
        ["name", "entity_type", "country", "pledged_total", "confirmed_total", "opportunity_count"],
        [
            [r["name"], r["entity_type"], r["country"], r["pledged_total"], r["confirmed_total"], r["opportunity_count"]]
            for r in snapshot.top_entity_rows
        ],
    )

    # Overdue opportunities
    _write_section(
        writer,
        "OVERDUE_OPPORTUNITIES",
        ["deadline", "title", "external_entity", "legal_entity", "stage", "currency", "expected_amount"],
        [
            [r["deadline"], r["title"], r["external_entity"], r["legal_entity"], r["stage"], r["currency"], r["expected_amount"]]
            for r in snapshot.overdue_rows
        ],
    )

    # Upcoming opportunities
    _write_section(
        writer,
        "UPCOMING_OPPORTUNITIES_30_DAYS",
        ["deadline", "title", "external_entity", "legal_entity", "stage", "currency", "expected_amount"],
        [
            [r["deadline"], r["title"], r["external_entity"], r["legal_entity"], r["stage"], r["currency"], r["expected_amount"]]
            for r in snapshot.upcoming_rows
        ],
    )

    # Recent interactions
    _write_section(
        writer,
        "RECENT_INTERACTIONS",
        ["created_at", "external_entity", "interaction_type", "status", "subject", "assigned_to"],
        [
            [r["created_at"], r["external_entity"], r["interaction_type"], r["status"], r["subject"], r["assigned_to"]]
            for r in snapshot.recent_interaction_rows
        ],
    )

    content = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content, content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="advancement_board_snapshot_{snapshot.as_of_date}.csv"'
    )
    return response
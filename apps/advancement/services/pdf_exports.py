# apps/advancement/services/pdf_exports.py

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from decimal import Decimal

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT

from .board_snapshot import BoardSnapshot


# -----------------------------
# Helpers
# -----------------------------

def _safe_str(value) -> str:
    """Convert values safely for rendering."""
    if value is None:
        return "-"
    return str(value)


def _fmt_money(value) -> str:
    """Format decimal-like values for report display."""
    if value is None:
        return "-"
    try:
        d = Decimal(value)
        return f"{d:,.2f}"
    except Exception:
        return str(value)


def _logo_path(*parts: str) -> str | None:
    """Resolve a logo path inside static directory."""
    base = Path(settings.BASE_DIR)
    candidate = base.joinpath(*parts)
    return str(candidate) if candidate.exists() else None


def _table_style(header_bg=colors.HexColor("#0f172a")):
    """Reusable table style."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def _build_kpi_table(snapshot: BoardSnapshot):
    """Top summary KPI table."""
    data = [
        ["Metric", "Value"],
        ["Generated At", _safe_str(snapshot.generated_at)],
        ["As Of Date", _safe_str(snapshot.as_of_date)],
        ["Total Pledged", _fmt_money(snapshot.pledged_total)],
        ["Total Confirmed", _fmt_money(snapshot.confirmed_total)],
        ["Pipeline Value (planning)", _fmt_money(snapshot.pipeline_value)],
        ["Approval Rate %", _safe_str(snapshot.approval_rate)],
        ["Overdue Follow-ups", _safe_str(snapshot.overdue_followups)],
        ["Follow-ups Due Today", _safe_str(snapshot.due_today_followups)],
        ["External Entities", _safe_str(snapshot.entity_count)],
        ["Opportunities", _safe_str(snapshot.opp_count)],
        ["Commitments", _safe_str(snapshot.commitment_count)],
        ["Active Pipeline", _safe_str(snapshot.active_pipeline_count)],
    ]
    tbl = Table(data, colWidths=[75 * mm, 95 * mm], repeatRows=1)
    tbl.setStyle(_table_style())
    return tbl


def _build_stage_table(snapshot: BoardSnapshot):
    """Stage distribution table."""
    rows = [["Stage", "Count"]]
    for r in snapshot.stage_rows:
        rows.append([_safe_str(r["label"]), _safe_str(r["count"])])
    tbl = Table(rows, colWidths=[110 * mm, 60 * mm], repeatRows=1)
    tbl.setStyle(_table_style(colors.HexColor("#1d4ed8")))
    return tbl


def _build_top_entities_table(snapshot: BoardSnapshot):
    """Top entities funding table."""
    rows = [["Entity", "Type", "Country", "Pledged", "Confirmed", "Opps"]]
    for r in snapshot.top_entity_rows[:10]:
        rows.append([
            _safe_str(r["name"]),
            _safe_str(r["entity_type"]),
            _safe_str(r["country"]),
            _fmt_money(r["pledged_total"]),
            _fmt_money(r["confirmed_total"]),
            _safe_str(r["opportunity_count"]),
        ])
    if len(rows) == 1:
        rows.append(["No data", "-", "-", "-", "-", "-"])

    tbl = Table(
        rows,
        colWidths=[55 * mm, 28 * mm, 18 * mm, 25 * mm, 25 * mm, 14 * mm],
        repeatRows=1
    )
    tbl.setStyle(_table_style(colors.HexColor("#7c3aed")))
    return tbl


def _build_legal_entities_table(snapshot: BoardSnapshot):
    """Legal entities summary table."""
    rows = [["Legal Entity", "Country", "Base CCY", "Pledged", "Confirmed"]]
    for r in snapshot.legal_entity_rows:
        rows.append([
            _safe_str(r["name"]),
            _safe_str(r["country"]),
            _safe_str(r["base_currency"]),
            _fmt_money(r["total_pledged"]),
            _fmt_money(r["total_confirmed"]),
        ])
    if len(rows) == 1:
        rows.append(["No data", "-", "-", "-", "-"])

    tbl = Table(
        rows,
        colWidths=[60 * mm, 20 * mm, 20 * mm, 35 * mm, 35 * mm],
        repeatRows=1
    )
    tbl.setStyle(_table_style(colors.HexColor("#0ea5e9")))
    return tbl


def _build_opps_table(title: str, rows_data: list[dict], header_color: str):
    """Reusable opportunities table (overdue/upcoming)."""
    rows = [["Deadline", "Opportunity", "Entity", "Stage", "Expected"]]
    for r in rows_data[:20]:
        rows.append([
            _safe_str(r["deadline"]),
            _safe_str(r["title"]),
            _safe_str(r["external_entity"]),
            _safe_str(r["stage"]),
            f'{_safe_str(r["currency"])} {_fmt_money(r["expected_amount"])}',
        ])
    if len(rows) == 1:
        rows.append(["-", "No items", "-", "-", "-"])

    tbl = Table(
        rows,
        colWidths=[22 * mm, 55 * mm, 48 * mm, 28 * mm, 35 * mm],
        repeatRows=1
    )
    tbl.setStyle(_table_style(colors.HexColor(header_color)))
    return tbl


def _build_recent_interactions_table(snapshot: BoardSnapshot):
    """Recent interactions table."""
    rows = [["Created", "Entity", "Type", "Status", "Subject", "Assigned To"]]
    for r in snapshot.recent_interaction_rows[:15]:
        rows.append([
            _safe_str(r["created_at"]),
            _safe_str(r["external_entity"]),
            _safe_str(r["interaction_type"]),
            _safe_str(r["status"]),
            _safe_str(r["subject"]),
            _safe_str(r["assigned_to"]),
        ])
    if len(rows) == 1:
        rows.append(["-", "-", "-", "-", "No interactions", "-"])

    tbl = Table(
        rows,
        colWidths=[28 * mm, 42 * mm, 25 * mm, 22 * mm, 45 * mm, 25 * mm],
        repeatRows=1
    )
    tbl.setStyle(_table_style(colors.HexColor("#334155")))
    return tbl


def _build_header(story, styles):
    """PDF header with logos and title."""
    logo_word = _logo_path("static", "logo", "TownLIT.png")
    logo_mark = _logo_path("static", "logo", "TownLITLogo.png")

    # Header row: graphic logo + title block + wordmark
    row = []

    if logo_mark:
        row.append(Image(logo_mark, width=18 * mm, height=18 * mm))
    else:
        row.append("")

    title_html = (
        "<b>TownLIT Advancement</b><br/>"
        "Board Snapshot Report<br/>"
        f"<font size='8' color='#475569'>Generated: {timezone.localtime().strftime('%Y-%m-%d %H:%M')}</font>"
    )
    row.append(Paragraph(title_html, styles["HeaderTitle"]))

    if logo_word:
        # Word logo may be wide, keep height compact
        row.append(Image(logo_word, width=38 * mm, height=12 * mm))
    else:
        row.append("")

    header_tbl = Table(row and [row], colWidths=[22 * mm, 120 * mm, 40 * mm])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "LEFT"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    story.append(header_tbl)
    story.append(Spacer(1, 4 * mm))


def _footer(canvas, doc):
    """Page footer."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(15 * mm, 10 * mm, "TownLIT Advancement • Board Snapshot")
    canvas.drawRightString(195 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_board_snapshot_pdf_response(snapshot: BoardSnapshot) -> HttpResponse:
    """Create printable A4 PDF response for board snapshot."""
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title="TownLIT Advancement Board Snapshot",
        author="TownLIT",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="HeaderTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
        spaceBefore=4,
    ))
    styles.add(ParagraphStyle(
        name="Muted",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),
    ))
    styles.add(ParagraphStyle(
        name="RightNote",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#64748b"),
    ))

    story = []

    # Header
    _build_header(story, styles)

    # Intro notes
    story.append(Paragraph(
        "This report is a board-ready snapshot of TownLIT Advancement pipeline, commitments, and follow-up activity.",
        styles["Muted"]
    ))
    story.append(Paragraph(
        "Note: Pipeline Value is a planning metric and may include mixed currencies.",
        styles["Muted"]
    ))
    story.append(Spacer(1, 4 * mm))

    # Page 1 summary
    story.append(Paragraph("Summary KPIs", styles["SectionTitle"]))
    story.append(_build_kpi_table(snapshot))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Opportunity Stage Distribution", styles["SectionTitle"]))
    story.append(_build_stage_table(snapshot))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Top External Entities by Pledged", styles["SectionTitle"]))
    story.append(_build_top_entities_table(snapshot))

    # Page 2
    story.append(PageBreak())
    story.append(Paragraph("Legal Entity Totals", styles["SectionTitle"]))
    story.append(_build_legal_entities_table(snapshot))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Overdue Opportunities", styles["SectionTitle"]))
    story.append(_build_opps_table("Overdue", snapshot.overdue_rows, "#dc2626"))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Upcoming Deadlines (Next 30 Days)", styles["SectionTitle"]))
    story.append(_build_opps_table("Upcoming", snapshot.upcoming_rows, "#ea580c"))

    # Page 3
    story.append(PageBreak())
    story.append(Paragraph("Recent Interactions", styles["SectionTitle"]))
    story.append(_build_recent_interactions_table(snapshot))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        "Generated from Advancement Admin • Internal board use",
        styles["RightNote"]
    ))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="advancement_board_snapshot_{snapshot.as_of_date}.pdf"'
    )
    return response
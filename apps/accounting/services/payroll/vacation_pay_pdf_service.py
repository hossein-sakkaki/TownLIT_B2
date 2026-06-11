# apps/accounting/services/payroll/vacation_pay_pdf_service.py

from io import BytesIO
from decimal import Decimal

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from apps.accounting.models import PayStub


ZERO = Decimal("0.00")


class VacationPayPDFService:
    """
    Generates vacation pay statement PDF.
    """

    employer_name = "TownLIT Society"
    employer_address = "Coquitlam, British Columbia, Canada"
    currency = "CAD"

    def build_pdf(self, *, pay_stub: PayStub) -> bytes:
        """
        Return vacation pay PDF bytes.
        """

        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            rightMargin=0.55 * inch,
            leftMargin=0.55 * inch,
            topMargin=0.55 * inch,
            bottomMargin=0.55 * inch,
            title=f"Vacation Pay Statement - {pay_stub.employee.display_name}",
            author=self.employer_name,
        )

        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="SectionTitle",
                parent=styles["Heading3"],
                fontSize=12,
                leading=14,
                textColor=colors.HexColor("#0F2D3A"),
                spaceAfter=5,
            )
        )
        styles.add(
            ParagraphStyle(
                name="SmallNote",
                parent=styles["Normal"],
                fontSize=8,
                leading=10,
                textColor=colors.HexColor("#555555"),
            )
        )

        story = []

        story.append(Paragraph(f"<b>{self.employer_name}</b>", styles["Title"]))
        story.append(Paragraph("<b>Vacation Pay Statement</b>", styles["Heading2"]))
        story.append(Spacer(1, 8))

        story.append(self._identity_table(pay_stub=pay_stub))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Vacation Pay Summary", styles["SectionTitle"]))
        story.append(self._vacation_summary_table(pay_stub=pay_stub))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Deductions", styles["SectionTitle"]))
        story.append(self._deductions_table(pay_stub=pay_stub))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Payment Status", styles["SectionTitle"]))
        story.append(self._payment_table(pay_stub=pay_stub))
        story.append(Spacer(1, 12))

        story.append(
            Paragraph(
                "This vacation pay statement is generated from TownLIT payroll records. "
                "Vacation pay is processed through payroll and may be subject to CPP, EI, and income tax deductions.",
                styles["SmallNote"],
            )
        )
        story.append(
            Paragraph(
                f"Generated at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles["SmallNote"],
            )
        )

        doc.build(story)
        return buffer.getvalue()

    def _identity_table(self, *, pay_stub: PayStub):
        """
        Build identity section.
        """

        pay_run = pay_stub.pay_run
        period = pay_run.pay_period
        employee = pay_stub.employee

        data = [
            ["Employer", self.employer_name],
            ["Employer Address", self.employer_address],
            ["Employee", employee.display_name],
            ["Province", employee.province_of_employment],
            ["Pay Period", f"{period.start_date} to {period.end_date}"],
            ["Pay Date", str(period.pay_date)],
            ["Pay Run", pay_run.run_number],
            ["Currency", self.currency],
        ]

        return self._table(data, col_widths=[2.0 * inch, 4.8 * inch], header=False)

    def _vacation_summary_table(self, *, pay_stub: PayStub):
        """
        Build vacation summary.
        """

        data = [
            ["Item", "Amount"],
            ["Vacation Pay Gross", self._money(pay_stub.vacation_pay_paid)],
            ["Taxable Earnings", self._money(pay_stub.taxable_earnings)],
            ["Net Vacation Pay", self._money(pay_stub.net_pay)],
        ]

        return self._table(data, col_widths=[3.8 * inch, 2.0 * inch], amount_cols={1})

    def _deductions_table(self, *, pay_stub: PayStub):
        """
        Build deductions section.
        """

        data = [
            ["Deduction Type", "Amount"],
            ["CPP", self._money(pay_stub.employee_cpp)],
            ["CPP2", self._money(pay_stub.employee_cpp2)],
            ["EI", self._money(pay_stub.employee_ei)],
            ["Federal Income Tax", self._money(pay_stub.federal_income_tax)],
            ["Provincial Income Tax", self._money(pay_stub.provincial_income_tax)],
            ["Total Deductions", self._money(pay_stub.total_employee_deductions)],
        ]

        return self._table(data, col_widths=[3.8 * inch, 2.0 * inch], amount_cols={1})

    def _payment_table(self, *, pay_stub: PayStub):
        """
        Build payment status.
        """

        data = [
            ["Item", "Value"],
            ["Net Vacation Pay", self._money(pay_stub.net_pay)],
            ["Actual Paid", self._money(pay_stub.actual_paid)],
            ["Remaining Payable", self._money(pay_stub.net_salary_payable)],
            ["Paid On", str(pay_stub.salary_paid_on or "")],
            ["Payment Method", pay_stub.get_salary_payment_method_display() if pay_stub.salary_payment_method else ""],
            ["Payment Reference", pay_stub.salary_payment_reference or pay_stub.payment_note],
        ]

        return self._table(data, col_widths=[3.8 * inch, 2.0 * inch], amount_cols={1})

    def _table(self, data, col_widths, amount_cols=None, header=True):
        """
        Build styled table.
        """

        amount_cols = amount_cols or set()
        table = Table(data, colWidths=col_widths)

        commands = [
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C2CC")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FB")]),
        ]

        if header:
            commands.extend(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2F3")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F2D3A")),
                ]
            )

        for col in amount_cols:
            commands.append(("ALIGN", (col, 1), (col, -1), "RIGHT"))

        table.setStyle(TableStyle(commands))
        return table

    def _money(self, value) -> str:
        """
        Format money.
        """

        value = value or ZERO
        return f"{value:,.2f}"
# apps/accounting/services/payroll/payroll_register_pdf_service.py

from io import BytesIO
from decimal import Decimal

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from apps.accounting.models import PayRun


ZERO = Decimal("0.00")


class PayrollRegisterPDFService:
    """
    Human-readable payroll register PDF for one pay run.
    """

    employer_name = "TownLIT Society"
    currency = "CAD"

    def build_pdf(self, *, pay_run: PayRun) -> bytes:
        """
        Return payroll register PDF bytes.
        """

        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(LETTER),
            rightMargin=0.45 * inch,
            leftMargin=0.45 * inch,
            topMargin=0.45 * inch,
            bottomMargin=0.45 * inch,
            title=f"Payroll Register - {pay_run.run_number}",
            author=self.employer_name,
        )

        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="SmallText",
                parent=styles["Normal"],
                fontSize=8,
                leading=10,
            )
        )
        styles.add(
            ParagraphStyle(
                name="SectionTitle",
                parent=styles["Heading3"],
                fontSize=12,
                leading=14,
                spaceAfter=6,
                textColor=colors.HexColor("#0F2D3A"),
            )
        )

        story = []

        story.append(Paragraph(f"<b>{self.employer_name}</b>", styles["Title"]))
        story.append(Paragraph("<b>Payroll Register</b>", styles["Heading2"]))
        story.append(Spacer(1, 8))

        story.append(self._build_meta_table(pay_run=pay_run))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Payroll Summary", styles["SectionTitle"]))
        story.append(self._build_summary_table(pay_run=pay_run))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Remittance Summary", styles["SectionTitle"]))
        story.append(self._build_remittance_table(pay_run=pay_run))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Employee Payroll Details", styles["SectionTitle"]))
        story.append(self._build_employee_table(pay_run=pay_run))
        story.append(Spacer(1, 12))

        story.append(
            Paragraph(
                "Confidential payroll record. Prepared for internal accounting, payroll review, "
                "CRA support, and authorized administrative use.",
                styles["Italic"],
            )
        )
        story.append(
            Paragraph(
                f"Generated at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles["SmallText"],
            )
        )

        doc.build(story)
        return buffer.getvalue()

    def _build_meta_table(self, *, pay_run: PayRun):
        """
        Build pay run meta table.
        """

        period = pay_run.pay_period

        data = [
            ["Pay Run", pay_run.run_number, "Status", pay_run.status.upper()],
            ["Pay Period", f"{period.start_date} to {period.end_date}", "Pay Date", str(period.pay_date)],
            ["Payroll Year", str(period.tax_year), "Currency", self.currency],
            ["Generated For", self.employer_name, "Run Date", str(pay_run.run_date)],
        ]

        return self._table(
            data,
            col_widths=[1.3 * inch, 3.2 * inch, 1.2 * inch, 2.4 * inch],
            header=False,
        )

    def _build_summary_table(self, *, pay_run: PayRun):
        """
        Build high-level payroll totals.
        """

        data = [
            ["Metric", "Amount"],
            ["Gross Pay", self._money(pay_run.total_gross_pay)],
            ["Employee Deductions", self._money(pay_run.total_employee_deductions)],
            ["Employer Contributions", self._money(pay_run.total_employer_contributions)],
            ["Net Pay", self._money(pay_run.total_net_pay)],
            ["Actual Paid", self._money(pay_run.total_actual_paid)],
            ["Remaining Salary Payable", self._money(pay_run.total_salary_payable)],
            ["Total Remittance Due", self._money(pay_run.total_remittance_due)],
        ]

        return self._table(
            data,
            col_widths=[3.0 * inch, 1.8 * inch],
            amount_cols={1},
        )

    def _build_remittance_table(self, *, pay_run: PayRun):
        """
        Build CPP/tax remittance summary.
        """

        employee_cpp = ZERO
        employer_cpp = ZERO
        employee_cpp2 = ZERO
        employer_cpp2 = ZERO
        employee_ei = ZERO
        employer_ei = ZERO
        federal_tax = ZERO
        provincial_tax = ZERO

        for stub in pay_run.pay_stubs.all():
            employee_cpp += stub.employee_cpp or ZERO
            employer_cpp += stub.employer_cpp or ZERO
            employee_cpp2 += stub.employee_cpp2 or ZERO
            employer_cpp2 += stub.employer_cpp2 or ZERO
            employee_ei += stub.employee_ei or ZERO
            employer_ei += stub.employer_ei or ZERO
            federal_tax += stub.federal_income_tax or ZERO
            provincial_tax += stub.provincial_income_tax or ZERO

        data = [
            ["Remittance Item", "Amount"],
            ["Employee CPP", self._money(employee_cpp)],
            ["Employer CPP", self._money(employer_cpp)],
            ["Employee CPP2", self._money(employee_cpp2)],
            ["Employer CPP2", self._money(employer_cpp2)],
            ["Employee EI", self._money(employee_ei)],
            ["Employer EI", self._money(employer_ei)],
            ["Federal Income Tax", self._money(federal_tax)],
            ["Provincial Income Tax", self._money(provincial_tax)],
            ["Total Remittance Due", self._money(pay_run.total_remittance_due)],
        ]

        return self._table(
            data,
            col_widths=[3.0 * inch, 1.8 * inch],
            amount_cols={1},
        )

    def _build_employee_table(self, *, pay_run: PayRun):
        """
        Build readable employee table.
        """

        data = [
            [
                "Employee",
                "Gross",
                "Deductions",
                "Net Pay",
                "Actual Paid",
                "Salary Payable",
                "Employer Cost",
                "Remittance Due",
                "Payment Note",
            ]
        ]

        for stub in pay_run.pay_stubs.select_related("employee").order_by(
            "employee__legal_last_name",
            "employee__legal_first_name",
        ):
            employer_cost = (stub.gross_salary or ZERO) + (stub.total_employer_contributions or ZERO)

            data.append(
                [
                    self._p(stub.employee.display_name),
                    self._money(stub.gross_salary),
                    self._money(stub.total_employee_deductions),
                    self._money(stub.net_pay),
                    self._money(stub.actual_paid),
                    self._money(stub.net_salary_payable),
                    self._money(employer_cost),
                    self._money(stub.total_remittance_due),
                    self._p(stub.payment_note),
                ]
            )

        return self._table(
            data,
            col_widths=[
                1.45 * inch,
                0.85 * inch,
                0.9 * inch,
                0.85 * inch,
                0.85 * inch,
                1.0 * inch,
                0.95 * inch,
                1.0 * inch,
                1.55 * inch,
            ],
            amount_cols={1, 2, 3, 4, 5, 6, 7},
        )

    def _table(self, data, col_widths, amount_cols=None, header=True):
        """
        Build styled table.
        """

        amount_cols = amount_cols or set()
        table = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)

        commands = [
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C2CC")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEADING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FB")]),
        ]

        if header:
            commands.extend(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2F3")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F2D3A")),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
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

    def _p(self, value):
        """
        Wrap text safely.
        """

        styles = getSampleStyleSheet()
        return Paragraph(str(value or ""), styles["Normal"])
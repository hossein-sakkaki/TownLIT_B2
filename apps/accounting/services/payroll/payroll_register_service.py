# apps/accounting/services/payroll/payroll_register_service.py

from apps.accounting.models import PayRun
from apps.accounting.reports.exporters import (
    CSVReportExporter,
    XLSXReportExporter,
    PDFReportExporter,
)
from apps.accounting.services.payroll.payroll_register_pdf_service import PayrollRegisterPDFService


class PayrollRegisterService:
    """
    Builds payroll register exports for a pay run.
    """

    headers = [
        "Employee",
        "Gross Salary",
        "Vacation Earned",
        "Vacation Paid",
        "Sick Pay",
        "Taxable Benefits",
        "Pensionable Earnings",
        "Insurable Earnings",
        "Taxable Earnings",
        "Employee CPP",
        "Employee CPP2",
        "Employee EI",
        "Federal Tax",
        "Provincial Tax",
        "Total Employee Deductions",
        "Employer CPP",
        "Employer CPP2",
        "Employer EI",
        "Total Employer Contributions",
        "Net Pay",
        "Actual Paid",
        "Salary Payable",
        "Remittance Due",
        "Payment Note",
    ]

    def build_rows(self, *, pay_run: PayRun) -> list[list]:
        """
        Build register rows.
        """

        rows = []

        for stub in pay_run.pay_stubs.select_related("employee").order_by(
            "employee__legal_last_name",
            "employee__legal_first_name",
        ):
            rows.append(
                [
                    stub.employee.display_name,
                    str(stub.gross_salary),
                    str(stub.vacation_pay_earned),
                    str(stub.vacation_pay_paid),
                    str(stub.sick_pay_paid),
                    str(stub.taxable_benefits),
                    str(stub.pensionable_earnings),
                    str(stub.insurable_earnings),
                    str(stub.taxable_earnings),
                    str(stub.employee_cpp),
                    str(stub.employee_cpp2),
                    str(stub.employee_ei),
                    str(stub.federal_income_tax),
                    str(stub.provincial_income_tax),
                    str(stub.total_employee_deductions),
                    str(stub.employer_cpp),
                    str(stub.employer_cpp2),
                    str(stub.employer_ei),
                    str(stub.total_employer_contributions),
                    str(stub.net_pay),
                    str(stub.actual_paid),
                    str(stub.net_salary_payable),
                    str(stub.total_remittance_due),
                    stub.payment_note,
                ]
            )

        rows.append(
            [
                "TOTAL",
                str(pay_run.total_gross_pay),
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                str(pay_run.total_employee_deductions),
                "",
                "",
                "",
                str(pay_run.total_employer_contributions),
                str(pay_run.total_net_pay),
                str(pay_run.total_actual_paid),
                str(pay_run.total_salary_payable),
                str(pay_run.total_remittance_due),
                "",
            ]
        )

        return rows

    def export(self, *, pay_run: PayRun, file_format: str) -> tuple[bytes, str, str]:
        """
        Export payroll register.

        Returns: content, filename, content_type_key
        """

        file_format = file_format.lower()
        title = f"Payroll Register - {pay_run.run_number}"
        period_label = (
            f"{pay_run.pay_period.start_date} to {pay_run.pay_period.end_date}"
        )
        rows = self.build_rows(pay_run=pay_run)

        filename_base = f"payroll_register_{pay_run.run_number}"

        if file_format == "csv":
            content = CSVReportExporter().export(
                headers=self.headers,
                rows=rows,
                title=title,
                period_label=period_label,
                generated_by="Accounting Admin",
                environment_label="Production",
            )
            return content, f"{filename_base}.csv", "csv"

        if file_format == "xlsx":
            content = XLSXReportExporter().export(
                sheet_name="Payroll Register",
                headers=self.headers,
                rows=rows,
                title=title,
                period_label=period_label,
                generated_by="Accounting Admin",
                environment_label="Production",
            )
            return content, f"{filename_base}.xlsx", "xlsx"

        if file_format == "pdf":
            content = PayrollRegisterPDFService().build_pdf(pay_run=pay_run)
            return content, f"{filename_base}.pdf", "pdf"

        raise ValueError("Unsupported payroll register format.")
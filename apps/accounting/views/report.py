# apps/accounting/views/report.py

from datetime import datetime

from reportlab.lib.units import mm
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounting.reports.exporters.base import build_period_label
from apps.accounting.reports.service import AccountingReportService
from apps.accounting.reports.exporters import (
    CSVReportExporter,
    XLSXReportExporter,
    PDFReportExporter,
)
from apps.accounting.reports.http import build_file_response


def parse_date(value: str | None):
    """
    Parse YYYY-MM-DD date string.
    """

    if not value:
        return None

    return datetime.strptime(value, "%Y-%m-%d").date()


class BaseReportView(APIView):
    """
    Base class for accounting report endpoints.
    """

    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]
    report_service = AccountingReportService()

    def get_format(self, request):
        """
        Resolve export format.
        Avoid DRF reserved `format` query param.
        """

        return request.query_params.get("file_format", "json").lower()

    def export_or_json(
        self,
        *,
        request,
        title,
        headers,
        rows,
        filename_base,
        payload,
        date_from=None,
        date_to=None,
        logo_filename="TownLITLogo.png",
        pdf_col_widths=None,
        pdf_amount_columns=None,
    ):
        """
        Return JSON or branded file export.
        """

        file_format = self.get_format(request)

        if file_format == "json":
            return Response(payload)

        period_label = build_period_label(date_from, date_to)
        generated_by = str(request.user)
        environment_label = "Production"

        if file_format == "csv":
            content = CSVReportExporter().export(
                headers=headers,
                rows=rows,
                title=title,
                period_label=period_label,
                generated_by=generated_by,
                environment_label=environment_label,
            )
            return build_file_response(
                content=content,
                filename=f"{filename_base}.csv",
                file_format="csv",
            )

        if file_format == "xlsx":
            content = XLSXReportExporter().export(
                sheet_name=title[:31],
                headers=headers,
                rows=rows,
                title=title,
                period_label=period_label,
                generated_by=generated_by,
                environment_label=environment_label,
            )
            return build_file_response(
                content=content,
                filename=f"{filename_base}.xlsx",
                file_format="xlsx",
            )

        if file_format == "pdf":
            content = PDFReportExporter().export(
                title=title,
                headers=headers,
                rows=rows,
                period_label=period_label,
                generated_by=generated_by,
                environment_label=environment_label,
                logo_filename=logo_filename,
                col_widths=pdf_col_widths,
                amount_columns=pdf_amount_columns,
            )
            return build_file_response(
                content=content,
                filename=f"{filename_base}.pdf",
                file_format="pdf",
            )

        return Response({"detail": "Unsupported format."}, status=400)


class TrialBalanceReportView(BaseReportView):
    """
    Trial balance endpoint.
    """

    def get(self, request):
        date_from = parse_date(request.query_params.get("date_from"))
        date_to = parse_date(request.query_params.get("date_to"))

        report = self.report_service.get_trial_balance(
            date_from=date_from,
            date_to=date_to,
        )

        headers = [
            "Account Code",
            "Account Name",
            "Account Type",
            "Normal Balance",
            "Total Debit",
            "Total Credit",
            "Balance",
        ]
        rows = [
            [
                row.account_code,
                row.account_name,
                row.account_type,
                row.normal_balance,
                str(row.total_debit),
                str(row.total_credit),
                str(row.balance),
            ]
            for row in report.rows
        ]

        payload = {
            "title": report.title,
            "date_from": report.date_from,
            "date_to": report.date_to,
            "total_debit": str(report.total_debit),
            "total_credit": str(report.total_credit),
            "rows": [
                {
                    "account_code": row.account_code,
                    "account_name": row.account_name,
                    "account_type": row.account_type,
                    "normal_balance": row.normal_balance,
                    "total_debit": str(row.total_debit),
                    "total_credit": str(row.total_credit),
                    "balance": str(row.balance),
                }
                for row in report.rows
            ],
        }

        pdf_col_widths = [
            22 * mm,  # Account Code
            42 * mm,  # Account Name
            28 * mm,  # Account Type
            26 * mm,  # Normal Balance
            24 * mm,  # Total Debit
            24 * mm,  # Total Credit
            24 * mm,  # Balance
        ]
        pdf_amount_columns = {4, 5, 6}

        return self.export_or_json(
            request=request,
            title=report.title,
            headers=headers,
            rows=rows,
            filename_base="trial_balance",
            payload=payload,
            date_from=report.date_from,
            date_to=report.date_to,
            logo_filename="TownLITLogo.png",
            pdf_col_widths=pdf_col_widths,
            pdf_amount_columns=pdf_amount_columns,
        )


class GeneralLedgerReportView(BaseReportView):
    """
    General ledger endpoint.
    """

    def get(self, request, account_code: str):
        date_from = parse_date(request.query_params.get("date_from"))
        date_to = parse_date(request.query_params.get("date_to"))

        report = self.report_service.get_general_ledger(
            account_code=account_code,
            date_from=date_from,
            date_to=date_to,
        )

        title = f"{report.title} - {report.account_code}"

        headers = [
            "Entry Number",
            "Entry Date",
            "Reference",
            "Description",
            "Source App",
            "Source Model",
            "Source Ref",
            "Line Memo",
            "Debit",
            "Credit",
            "Running Balance",
        ]
        rows = [
            [
                row.entry_number,
                row.entry_date.isoformat(),
                row.reference,
                row.description,
                row.source_app,
                row.source_model,
                row.source_ref,
                row.line_memo,
                str(row.debit),
                str(row.credit),
                str(row.running_balance),
            ]
            for row in report.rows
        ]

        payload = {
            "title": title,
            "account_code": report.account_code,
            "account_name": report.account_name,
            "account_type": report.account_type,
            "normal_balance": report.normal_balance,
            "date_from": report.date_from,
            "date_to": report.date_to,
            "total_debit": str(report.total_debit),
            "total_credit": str(report.total_credit),
            "ending_balance": str(report.ending_balance),
            "rows": [
                {
                    "entry_number": row.entry_number,
                    "entry_date": row.entry_date,
                    "reference": row.reference,
                    "description": row.description,
                    "source_app": row.source_app,
                    "source_model": row.source_model,
                    "source_ref": row.source_ref,
                    "line_memo": row.line_memo,
                    "debit": str(row.debit),
                    "credit": str(row.credit),
                    "running_balance": str(row.running_balance),
                }
                for row in report.rows
            ],
        }

        pdf_col_widths = [
            22 * mm,  # Entry Number
            18 * mm,  # Entry Date
            18 * mm,  # Reference
            34 * mm,  # Description
            18 * mm,  # Source App
            18 * mm,  # Source Model
            18 * mm,  # Source Ref
            30 * mm,  # Line Memo
            16 * mm,  # Debit
            16 * mm,  # Credit
            22 * mm,  # Running Balance
        ]
        pdf_amount_columns = {8, 9, 10}

        return self.export_or_json(
            request=request,
            title=title,
            headers=headers,
            rows=rows,
            filename_base=f"general_ledger_{report.account_code}",
            payload=payload,
            date_from=report.date_from,
            date_to=report.date_to,
            logo_filename="TownLITLogo.png",
            pdf_col_widths=pdf_col_widths,
            pdf_amount_columns=pdf_amount_columns,
        )


class FounderBalanceSummaryView(BaseReportView):
    """
    Founder balance summary endpoint.
    """

    def get(self, request):
        date_from = parse_date(request.query_params.get("date_from"))
        date_to = parse_date(request.query_params.get("date_to"))

        founder_loan_account_code = request.query_params.get(
            "founder_loan_account_code",
            "2110",
        )
        founder_withdrawal_account_code = request.query_params.get(
            "founder_withdrawal_account_code",
            "3300",
        )

        report = self.report_service.get_founder_balance_summary(
            founder_loan_account_code=founder_loan_account_code,
            founder_withdrawal_account_code=founder_withdrawal_account_code,
            date_from=date_from,
            date_to=date_to,
        )

        headers = [
            "Founder Loan Account",
            "Founder Withdrawal Account",
            "Total Loans",
            "Total Withdrawals",
            "Net Founder Balance",
        ]
        rows = [[
            f"{report.founder_loan_account_code} - {report.founder_loan_account_name}",
            f"{report.founder_withdrawal_account_code} - {report.founder_withdrawal_account_name}",
            str(report.total_loans),
            str(report.total_withdrawals),
            str(report.net_founder_balance),
        ]]

        payload = {
            "title": report.title,
            "date_from": report.date_from,
            "date_to": report.date_to,
            "founder_loan_account_code": report.founder_loan_account_code,
            "founder_loan_account_name": report.founder_loan_account_name,
            "founder_withdrawal_account_code": report.founder_withdrawal_account_code,
            "founder_withdrawal_account_name": report.founder_withdrawal_account_name,
            "total_loans": str(report.total_loans),
            "total_withdrawals": str(report.total_withdrawals),
            "net_founder_balance": str(report.net_founder_balance),
        }

        pdf_col_widths = [
            52 * mm,  # Founder Loan Account
            52 * mm,  # Founder Withdrawal Account
            26 * mm,  # Total Loans
            26 * mm,  # Total Withdrawals
            30 * mm,  # Net Founder Balance
        ]
        pdf_amount_columns = {2, 3, 4}

        return self.export_or_json(
            request=request,
            title=report.title,
            headers=headers,
            rows=rows,
            filename_base="founder_balance_summary",
            payload=payload,
            date_from=report.date_from,
            date_to=report.date_to,
            logo_filename="TownLITLogo.png",
            pdf_col_widths=pdf_col_widths,
            pdf_amount_columns=pdf_amount_columns,
        )


class MonthlySummaryReportView(BaseReportView):
    """
    Monthly summary endpoint.
    """

    def get(self, request):
        date_from = parse_date(request.query_params.get("date_from"))
        date_to = parse_date(request.query_params.get("date_to"))

        report = self.report_service.get_monthly_summary(
            date_from=date_from,
            date_to=date_to,
        )

        headers = [
            "Period",
            "Revenue Total",
            "Expense Total",
            "Net Result",
        ]
        rows = [
            [
                row.period,
                str(row.revenue_total),
                str(row.expense_total),
                str(row.net_result),
            ]
            for row in report.rows
        ]

        payload = {
            "title": report.title,
            "date_from": report.date_from,
            "date_to": report.date_to,
            "total_revenue": str(report.total_revenue),
            "total_expense": str(report.total_expense),
            "total_net_result": str(report.total_net_result),
            "rows": [
                {
                    "period": row.period,
                    "revenue_total": str(row.revenue_total),
                    "expense_total": str(row.expense_total),
                    "net_result": str(row.net_result),
                }
                for row in report.rows
            ],
        }

        pdf_col_widths = [
            34 * mm,  # Period
            42 * mm,  # Revenue Total
            42 * mm,  # Expense Total
            42 * mm,  # Net Result
        ]
        pdf_amount_columns = {1, 2, 3}

        return self.export_or_json(
            request=request,
            title=report.title,
            headers=headers,
            rows=rows,
            filename_base="monthly_summary",
            payload=payload,
            date_from=report.date_from,
            date_to=report.date_to,
            logo_filename="TownLITLogo.png",
            pdf_col_widths=pdf_col_widths,
            pdf_amount_columns=pdf_amount_columns,
        )
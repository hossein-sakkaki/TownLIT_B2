# apps/accounting/views/fund_report.py

from datetime import datetime

from reportlab.lib.units import mm
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounting.reports.exporters.base import build_period_label
from apps.accounting.reports.fund_service import FundReportService
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


class BaseFundReportView(APIView):
    """
    Base view for fund reports.
    """

    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]
    report_service = FundReportService()

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


class FundSummaryReportView(BaseFundReportView):
    """
    Fund summary endpoint.
    """

    def get(self, request, fund_code: str):
        date_from = parse_date(request.query_params.get("date_from"))
        date_to = parse_date(request.query_params.get("date_to"))

        payload = self.report_service.get_fund_summary(
            fund_code=fund_code,
            date_from=date_from,
            date_to=date_to,
        )

        headers = [
            "Fund Code",
            "Fund Name",
            "Fund Type",
            "Restricted",
            "Total Awarded",
            "Revenue Total",
            "Expense Total",
            "Remaining Balance",
        ]
        rows = [[
            payload["fund_code"],
            payload["fund_name"],
            payload["fund_type"],
            str(payload["is_restricted"]),
            payload["total_awarded"],
            payload["revenue_total"],
            payload["expense_total"],
            payload["remaining_balance"],
        ]]

        pdf_col_widths = [
            24 * mm,  # Fund Code
            38 * mm,  # Fund Name
            22 * mm,  # Fund Type
            18 * mm,  # Restricted
            24 * mm,  # Total Awarded
            24 * mm,  # Revenue Total
            24 * mm,  # Expense Total
            28 * mm,  # Remaining Balance
        ]
        pdf_amount_columns = {4, 5, 6, 7}

        return self.export_or_json(
            request=request,
            title=payload["title"],
            headers=headers,
            rows=rows,
            filename_base=f"fund_summary_{fund_code}",
            payload=payload,
            date_from=payload.get("date_from"),
            date_to=payload.get("date_to"),
            logo_filename="TownLITLogo.png",
            pdf_col_widths=pdf_col_widths,
            pdf_amount_columns=pdf_amount_columns,
        )


class FundLedgerReportView(BaseFundReportView):
    """
    Fund ledger endpoint.
    """

    def get(self, request, fund_code: str):
        date_from = parse_date(request.query_params.get("date_from"))
        date_to = parse_date(request.query_params.get("date_to"))

        payload = self.report_service.get_fund_ledger(
            fund_code=fund_code,
            date_from=date_from,
            date_to=date_to,
        )

        headers = [
            "Entry Number",
            "Entry Date",
            "Account Code",
            "Account Name",
            "Reference",
            "Description",
            "Memo",
            "Budget Code",
            "Debit",
            "Credit",
            "Revenue Effect",
            "Expense Effect",
        ]
        rows = [
            [
                row["entry_number"],
                row["entry_date"].isoformat(),
                row["account_code"],
                row["account_name"],
                row["reference"],
                row["description"],
                row["memo"],
                row["budget_code"],
                row["debit"],
                row["credit"],
                row["revenue_effect"],
                row["expense_effect"],
            ]
            for row in payload["rows"]
        ]

        pdf_col_widths = [
            18 * mm,  # Entry Number
            16 * mm,  # Entry Date
            18 * mm,  # Account Code
            24 * mm,  # Account Name
            18 * mm,  # Reference
            28 * mm,  # Description
            24 * mm,  # Memo
            18 * mm,  # Budget Code
            14 * mm,  # Debit
            14 * mm,  # Credit
            18 * mm,  # Revenue Effect
            18 * mm,  # Expense Effect
        ]
        pdf_amount_columns = {8, 9, 10, 11}

        return self.export_or_json(
            request=request,
            title=payload["title"],
            headers=headers,
            rows=rows,
            filename_base=f"fund_ledger_{fund_code}",
            payload=payload,
            date_from=payload.get("date_from"),
            date_to=payload.get("date_to"),
            logo_filename="TownLITLogo.png",
            pdf_col_widths=pdf_col_widths,
            pdf_amount_columns=pdf_amount_columns,
        )


class BudgetVsActualReportView(BaseFundReportView):
    """
    Budget vs actual endpoint.
    """

    def get(self, request, fund_code: str):
        date_from = parse_date(request.query_params.get("date_from"))
        date_to = parse_date(request.query_params.get("date_to"))

        payload = self.report_service.get_budget_vs_actual(
            fund_code=fund_code,
            date_from=date_from,
            date_to=date_to,
        )

        headers = [
            "Budget Code",
            "Budget Line Code",
            "Budget Line Name",
            "Approved Amount",
            "Actual Amount",
            "Remaining Amount",
        ]
        rows = [
            [
                row["budget_code"],
                row["budget_line_code"],
                row["budget_line_name"],
                row["approved_amount"],
                row["actual_amount"],
                row["remaining_amount"],
            ]
            for row in payload["rows"]
        ]

        pdf_col_widths = [
            28 * mm,  # Budget Code
            30 * mm,  # Budget Line Code
            46 * mm,  # Budget Line Name
            26 * mm,  # Approved Amount
            26 * mm,  # Actual Amount
            26 * mm,  # Remaining Amount
        ]
        pdf_amount_columns = {3, 4, 5}

        return self.export_or_json(
            request=request,
            title=payload["title"],
            headers=headers,
            rows=rows,
            filename_base=f"budget_vs_actual_{fund_code}",
            payload=payload,
            date_from=payload.get("date_from"),
            date_to=payload.get("date_to"),
            logo_filename="TownLITLogo.png",
            pdf_col_widths=pdf_col_widths,
            pdf_amount_columns=pdf_amount_columns,
        )
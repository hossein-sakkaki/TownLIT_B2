# apps/accounting/reports/fund_service.py

from .filters import ReportFilter
from .fund_queries import (
    build_fund_summary,
    build_fund_ledger,
    build_budget_vs_actual,
)


class FundReportService:
    """
    Facade service for fund and grant reports.
    """

    def get_fund_summary(self, *, fund_code: str, date_from=None, date_to=None, include_draft=False):
        return build_fund_summary(
            fund_code=fund_code,
            report_filter=ReportFilter(
                date_from=date_from,
                date_to=date_to,
                include_draft=include_draft,
            ),
        )

    def get_fund_ledger(self, *, fund_code: str, date_from=None, date_to=None, include_draft=False):
        return build_fund_ledger(
            fund_code=fund_code,
            report_filter=ReportFilter(
                date_from=date_from,
                date_to=date_to,
                include_draft=include_draft,
            ),
        )

    def get_budget_vs_actual(self, *, fund_code: str, date_from=None, date_to=None, include_draft=False):
        return build_budget_vs_actual(
            fund_code=fund_code,
            report_filter=ReportFilter(
                date_from=date_from,
                date_to=date_to,
                include_draft=include_draft,
            ),
        )
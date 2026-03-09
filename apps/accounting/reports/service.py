# apps/accounting/reports/service.py

from .filters import ReportFilter
from .queries import (
    build_trial_balance,
    build_general_ledger,
    build_founder_balance_summary,
    build_monthly_summary,
)


class AccountingReportService:
    """
    Facade service for accounting reports.
    """

    def get_trial_balance(self, *, date_from=None, date_to=None, include_draft=False):
        return build_trial_balance(
            ReportFilter(
                date_from=date_from,
                date_to=date_to,
                include_draft=include_draft,
            )
        )

    def get_general_ledger(
        self,
        *,
        account_code: str,
        date_from=None,
        date_to=None,
        include_draft=False,
    ):
        return build_general_ledger(
            account_code=account_code,
            report_filter=ReportFilter(
                date_from=date_from,
                date_to=date_to,
                include_draft=include_draft,
            ),
        )

    def get_founder_balance_summary(
        self,
        *,
        founder_loan_account_code: str,
        founder_withdrawal_account_code: str,
        date_from=None,
        date_to=None,
        include_draft=False,
    ):
        return build_founder_balance_summary(
            founder_loan_account_code=founder_loan_account_code,
            founder_withdrawal_account_code=founder_withdrawal_account_code,
            report_filter=ReportFilter(
                date_from=date_from,
                date_to=date_to,
                include_draft=include_draft,
            ),
        )

    def get_monthly_summary(self, *, date_from=None, date_to=None, include_draft=False):
        return build_monthly_summary(
            ReportFilter(
                date_from=date_from,
                date_to=date_to,
                include_draft=include_draft,
            )
        )
# apps/accounting/api/fund_report_urls.py

from django.urls import path

from ..views.fund_report import (
    FundSummaryReportView,
    FundLedgerReportView,
    BudgetVsActualReportView,
)

urlpatterns = [
    path(
        "fund-summary/<str:fund_code>/",
        FundSummaryReportView.as_view(),
        name="accounting-fund-summary",
    ),
    path(
        "fund-ledger/<str:fund_code>/",
        FundLedgerReportView.as_view(),
        name="accounting-fund-ledger",
    ),
    path(
        "budget-vs-actual/<str:fund_code>/",
        BudgetVsActualReportView.as_view(),
        name="accounting-budget-vs-actual",
    ),
]
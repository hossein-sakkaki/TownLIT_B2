# apps/accounting/urls/report.py

from django.urls import path

from ..views.report import (
    TrialBalanceReportView,
    GeneralLedgerReportView,
    FounderBalanceSummaryView,
    MonthlySummaryReportView,
)

urlpatterns = [
    path("trial-balance/", TrialBalanceReportView.as_view(), name="accounting-trial-balance"),
    path("general-ledger/<str:account_code>/", GeneralLedgerReportView.as_view(), name="accounting-general-ledger"),
    path("founder-balance-summary/", FounderBalanceSummaryView.as_view(), name="accounting-founder-balance-summary"),
    path("monthly-summary/", MonthlySummaryReportView.as_view(), name="accounting-monthly-summary"),
]
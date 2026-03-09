# apps/accounting/urls/index.py

from django.urls import include, path

urlpatterns = [
    path("reports/", include("apps.accounting.urls.reports")),
    path("fund-reports/", include("apps.accounting.urls.fund_reports")),
    path("dashboard/", include("apps.accounting.urls.dashboard")),
]
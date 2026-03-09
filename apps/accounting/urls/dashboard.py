# apps/accounting/api/dashboard_urls.py

from django.urls import path
from ..views.dashboard import AccountingDashboardView

urlpatterns = [
    path("", AccountingDashboardView.as_view(), name="accounting-dashboard"),
]
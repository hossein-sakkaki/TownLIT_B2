# apps/accounting/dashboard/service.py

from .queries import build_dashboard_payload


class AccountingDashboardService:
    """
    Facade for accounting dashboard.
    """

    def get_dashboard(self):
        return build_dashboard_payload()
# apps/accounting/admin/site.py

from django.contrib.admin import AdminSite
from django.urls import path


class AccountingAdminSite(AdminSite):
    """
    Dedicated admin site for accounting operations.
    Keeps financial management isolated from the main admin.
    """

    site_header = "TownLIT Accounting"
    site_title = "TownLIT Accounting Admin"
    index_title = "Accounting Management"

    index_template = "admin/accounting/index.html"
    app_index_template = "admin/accounting/app_index.html"

    def get_urls(self):
        """
        Add custom accounting admin URLs.
        """

        from .report_admin import accounting_report_hub
        from .dashboard_admin import accounting_dashboard_view
        from .period_generation_admin import generate_accounting_periods_view

        urls = super().get_urls()
        custom_urls = [
            path(
                "dashboard/",
                self.admin_view(accounting_dashboard_view),
                name="accounting-dashboard-admin",
            ),
            path(
                "reports/",
                self.admin_view(accounting_report_hub),
                name="accounting-report-hub",
            ),
            path(
                "reports-hub/",
                self.admin_view(accounting_report_hub),
                name="reports-hub",
            ),
            path(
                "periods/generate/",
                self.admin_view(generate_accounting_periods_view),
                name="accounting-generate-periods",
            ),
        ]
        return custom_urls + urls


accounting_admin_site = AccountingAdminSite(name="accounting_admin")
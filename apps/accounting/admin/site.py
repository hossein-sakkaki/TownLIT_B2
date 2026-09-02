# apps/accounting/admin/site.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-09-02.
#

from django.contrib.admin import AdminSite
from django.urls import path


class AccountingAdminSite(AdminSite):
    """
    Workflow-first admin site for accounting operations.
    """

    site_header = "TownLIT Accounting"
    site_title = "TownLIT Accounting"
    index_title = "Accounting Workspace"

    index_template = "admin/accounting/index.html"
    app_index_template = "admin/accounting/app_index.html"

    def index(self, request, extra_context=None):
        """
        Make the accounting home page operational instead of model-first.
        """

        from .workspace_admin import build_accounting_workspace_context

        context = {
            **(extra_context or {}),
            **build_accounting_workspace_context(include_operations=True),
        }
        return super().index(request, extra_context=context)

    def get_urls(self):
        """
        Add workflow and reporting URLs.
        """

        from .dashboard_admin import accounting_dashboard_view
        from .period_generation_admin import generate_accounting_periods_view
        from .report_admin import accounting_report_hub
        from .workspace_admin import banking_workspace_view, payroll_workspace_view
        from .money_admin import money_workspace_view, record_expense_view, record_income_view
        from .fixed_asset_admin import asset_workspace_view, post_depreciation_view, purchase_fixed_asset_view
        from .fund_workspace_admin import configure_fund_view, fund_detail_view, funds_workspace_view
        from .vendor_ap_admin import accounts_payable_workspace_view, ap_aging_export_view, pay_vendor_view
        from .customer_ar_admin import (
            accounts_receivable_workspace_view,
            ar_aging_export_view,
            customer_statement_export_view,
            invoice_print_view,
            receive_customer_payment_view,
        )

        urls = super().get_urls()
        custom_urls = [
            path(
                "dashboard/",
                self.admin_view(accounting_dashboard_view),
                name="accounting-dashboard-admin",
            ),
            path(
                "payroll/",
                self.admin_view(payroll_workspace_view),
                name="accounting-payroll-workspace",
            ),
            path(
                "banking/",
                self.admin_view(banking_workspace_view),
                name="accounting-banking-workspace",
            ),
            path(
                "money/",
                self.admin_view(money_workspace_view),
                name="accounting-money-workspace",
            ),
            path(
                "money/income/",
                self.admin_view(record_income_view),
                name="accounting-record-income",
            ),
            path(
                "money/expense/",
                self.admin_view(record_expense_view),
                name="accounting-record-expense",
            ),
            path(
                "assets/",
                self.admin_view(asset_workspace_view),
                name="accounting-asset-workspace",
            ),
            path(
                "assets/purchase/",
                self.admin_view(purchase_fixed_asset_view),
                name="accounting-purchase-fixed-asset",
            ),
            path(
                "assets/depreciation/post/",
                self.admin_view(post_depreciation_view),
                name="accounting-post-depreciation",
            ),
            path(
                "ap/",
                self.admin_view(accounts_payable_workspace_view),
                name="accounting-ap-workspace",
            ),
            path(
                "ap/vendor/<int:vendor_id>/pay/",
                self.admin_view(pay_vendor_view),
                name="accounting-ap-pay-vendor",
            ),
            path(
                "ap/aging.csv",
                self.admin_view(ap_aging_export_view),
                name="accounting-ap-aging-export",
            ),
            path(
                "ar/",
                self.admin_view(accounts_receivable_workspace_view),
                name="accounting-ar-workspace",
            ),
            path(
                "ar/customer/<int:customer_id>/receive/",
                self.admin_view(receive_customer_payment_view),
                name="accounting-ar-receive-customer",
            ),
            path(
                "ar/customer/<int:customer_id>/statement.csv",
                self.admin_view(customer_statement_export_view),
                name="accounting-ar-customer-statement",
            ),
            path(
                "ar/invoice/<int:invoice_id>/print/",
                self.admin_view(invoice_print_view),
                name="accounting-ar-invoice-print",
            ),
            path(
                "ar/aging.csv",
                self.admin_view(ar_aging_export_view),
                name="accounting-ar-aging-export",
            ),
            path(
                "funds/",
                self.admin_view(funds_workspace_view),
                name="accounting-funds-workspace",
            ),
            path(
                "funds/<int:fund_id>/",
                self.admin_view(fund_detail_view),
                name="accounting-fund-detail",
            ),
            path(
                "funds/<int:fund_id>/configure/",
                self.admin_view(configure_fund_view),
                name="accounting-fund-configure",
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

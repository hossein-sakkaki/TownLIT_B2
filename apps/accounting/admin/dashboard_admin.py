# apps/accounting/admin/dashboard_admin.py

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from apps.accounting.dashboard.service import AccountingDashboardService
from .site import accounting_admin_site


@staff_member_required
def accounting_dashboard_view(request):
    """
    Render dashboard inside accounting admin.
    """

    payload = AccountingDashboardService().get_dashboard()

    context = {
        **accounting_admin_site.each_context(request),
        "title": "Accounting Dashboard",
        "payload": payload,
    }
    return render(request, "admin/accounting/dashboard.html", context)
# apps/accounting/admin/period_generation_admin.py

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.urls import reverse

from apps.accounting.admin.forms import AccountingPeriodGenerationForm
from apps.accounting.services.period_generation_service import (
    generate_fiscal_year_periods,
)
from .site import accounting_admin_site


@staff_member_required
def generate_accounting_periods_view(request):
    """
    Generate TownLIT fiscal-year periods from the accounting admin.
    """

    form = AccountingPeriodGenerationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        result = generate_fiscal_year_periods(
            fy_start_year=form.cleaned_data["fy_start_year"],
            default_status=form.cleaned_data["default_status"],
        )

        messages.success(
            request,
            f"{result.created_or_updated_count} accounting periods created/updated for {result.fiscal_year_label}.",
        )

        return redirect(reverse("accounting_admin:accounting_accountingperiod_changelist"))

    context = {
        **accounting_admin_site.each_context(request),
        "title": "Generate Accounting Periods",
        "form": form,
    }
    return render(
        request,
        "admin/accounting/generate_periods.html",
        context,
    )
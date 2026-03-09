# apps/accounting/admin/report_admin.py

from urllib.parse import urlencode

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.urls import reverse

from apps.accounting.admin.forms import (
    AccountingReportHubForm,
    AccountingObjectReportForm,
)
from .site import accounting_admin_site


@staff_member_required
def accounting_report_hub(request):
    """
    Central report hub inside accounting admin.
    """

    report_form = AccountingReportHubForm(request.POST or None, prefix="main")
    object_form = AccountingObjectReportForm(request.POST or None, prefix="object")

    if request.method == "POST":
        if "generate_main_report" in request.POST and report_form.is_valid():
            return redirect(_build_main_report_url(report_form.cleaned_data))

        if "generate_object_report" in request.POST and object_form.is_valid():
            return redirect(_build_object_report_url(object_form.cleaned_data))

    context = {
        **accounting_admin_site.each_context(request),
        "title": "Accounting Reports",
        "report_form": report_form,
        "object_form": object_form,
    }
    return render(request, "admin/accounting/report_hub.html", context)


def _build_main_report_url(cleaned_data: dict) -> str:
    """
    Build report API URL for non-object reports.
    """

    report_type = cleaned_data["report_type"]

    params = {
        "file_format": cleaned_data["file_format"],
    }

    if cleaned_data.get("date_from"):
        params["date_from"] = cleaned_data["date_from"].isoformat()

    if cleaned_data.get("date_to"):
        params["date_to"] = cleaned_data["date_to"].isoformat()

    route_map = {
        "trial_balance": "accounting-trial-balance",
        "founder_balance_summary": "accounting-founder-balance-summary",
        "monthly_summary": "accounting-monthly-summary",
    }

    base_url = reverse(route_map[report_type])
    return f"{base_url}?{urlencode(params)}"


def _build_object_report_url(cleaned_data: dict) -> str:
    """
    Build report API URL for account/fund reports.
    """

    report_type = cleaned_data["report_type"]

    params = {
        "file_format": cleaned_data["file_format"],
    }

    if cleaned_data.get("date_from"):
        params["date_from"] = cleaned_data["date_from"].isoformat()

    if cleaned_data.get("date_to"):
        params["date_to"] = cleaned_data["date_to"].isoformat()

    if report_type == "general_ledger":
        base_url = reverse(
            "accounting-general-ledger",
            kwargs={"account_code": cleaned_data["account"].code},
        )
        return f"{base_url}?{urlencode(params)}"

    if report_type == "fund_summary":
        base_url = reverse(
            "accounting-fund-summary",
            kwargs={"fund_code": cleaned_data["fund"].code},
        )
        return f"{base_url}?{urlencode(params)}"

    if report_type == "fund_ledger":
        base_url = reverse(
            "accounting-fund-ledger",
            kwargs={"fund_code": cleaned_data["fund"].code},
        )
        return f"{base_url}?{urlencode(params)}"

    if report_type == "budget_vs_actual":
        base_url = reverse(
            "accounting-budget-vs-actual",
            kwargs={"fund_code": cleaned_data["fund"].code},
        )
        return f"{base_url}?{urlencode(params)}"

    raise ValueError("Unsupported object report type.")
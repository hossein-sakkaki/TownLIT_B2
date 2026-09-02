# apps/accounting/admin/fund_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from urllib.parse import urlencode

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.accounting.models import (
    Budget,
    BudgetLine,
    Fund,
    FundAllowedAccount,
    FundAllowedBudgetLine,
    FundPolicy,
)

from .site import accounting_admin_site


class FundPolicyInline(admin.StackedInline):
    model = FundPolicy
    extra = 0
    max_num = 1
    can_delete = False
    classes = ("collapse",)
    fields = (
        "mode",
        "enforce_rules",
        "enforce_date_window",
        "prevent_budget_overrun",
        "require_budget_line_for_expenses",
        "note",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")


class FundAllowedAccountInline(admin.TabularInline):
    model = FundAllowedAccount
    extra = 0
    autocomplete_fields = ("account",)
    classes = ("collapse",)
    fields = (
        "account",
        "allow_revenue",
        "allow_expense",
        "allow_asset",
        "allow_liability",
        "allow_equity",
        "created_at",
    )
    readonly_fields = ("created_at",)


class FundAllowedBudgetLineInline(admin.TabularInline):
    model = FundAllowedBudgetLine
    extra = 0
    autocomplete_fields = ("budget_line",)
    classes = ("collapse",)
    fields = ("budget_line", "created_at")
    readonly_fields = ("created_at",)


class BudgetLineInline(admin.TabularInline):
    model = BudgetLine
    extra = 0
    fields = (
        "code",
        "name",
        "approved_amount",
        "is_active",
        "sort_order",
        "created_at",
    )
    readonly_fields = ("created_at",)


@admin.register(Fund, site=accounting_admin_site)
class FundAdmin(admin.ModelAdmin):
    """
    Fund master data. Daily operations belong in the Fund Workspace.
    """

    list_display = (
        "code",
        "name",
        "fund_type",
        "status",
        "is_restricted",
        "total_awarded",
        "start_date",
        "end_date",
        "is_active",
        "workspace_link",
        "fund_reports_link",
    )
    list_filter = (
        "fund_type",
        "status",
        "is_restricted",
        "currency",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
        "description",
        "source_app",
        "source_model",
        "source_ref",
    )
    ordering = ("code",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (
        FundPolicyInline,
        FundAllowedAccountInline,
        FundAllowedBudgetLineInline,
    )

    fieldsets = (
        (
            "Fund",
            {
                "fields": (
                    "code",
                    "name",
                    "fund_type",
                    "status",
                    "description",
                    "is_restricted",
                    "total_awarded",
                    "currency",
                    "start_date",
                    "end_date",
                    "is_active",
                )
            },
        ),
        (
            "Source tracking",
            {
                "fields": ("source_app", "source_model", "source_ref"),
                "classes": ("collapse",),
            },
        ),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Workspace")
    def workspace_link(self, obj):
        if not obj or not obj.pk:
            return "-"
        url = reverse("accounting_admin:accounting-fund-detail", args=[obj.id])
        return format_html('<a class="button" href="{}">Open Fund</a>', url)

    @admin.display(description="Reports")
    def fund_reports_link(self, obj):
        if not obj or not obj.pk:
            return "-"
        summary = reverse("accounting-fund-summary", kwargs={"fund_code": obj.code})
        budget = reverse("accounting-budget-vs-actual", kwargs={"fund_code": obj.code})
        return format_html(
            '<a href="{}?{}">Summary</a> &nbsp; <a href="{}?{}">Budget</a>',
            summary,
            urlencode({"file_format": "xlsx"}),
            budget,
            urlencode({"file_format": "xlsx"}),
        )


@admin.register(Budget, site=accounting_admin_site)
class BudgetAdmin(admin.ModelAdmin):
    """
    Budget setup. Actual monitoring is surfaced in the Fund Workspace.
    """

    list_display = (
        "code",
        "name",
        "fund",
        "status",
        "start_date",
        "end_date",
        "currency",
        "is_active",
        "fund_workspace_link",
    )
    list_filter = ("status", "currency", "is_active")
    search_fields = (
        "code",
        "name",
        "description",
        "fund__code",
        "fund__name",
    )
    ordering = ("code",)
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("fund",)
    inlines = (BudgetLineInline,)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        fund_id = request.GET.get("fund")
        if fund_id and str(fund_id).isdigit():
            initial["fund"] = int(fund_id)
        return initial

    @admin.display(description="Fund Workspace")
    def fund_workspace_link(self, obj):
        if not obj or not obj.fund_id:
            return "-"
        url = reverse("accounting_admin:accounting-fund-detail", args=[obj.fund_id])
        return format_html('<a href="{}">Open fund</a>', url)


@admin.register(BudgetLine, site=accounting_admin_site)
class BudgetLineAdmin(admin.ModelAdmin):
    list_display = (
        "budget",
        "code",
        "name",
        "approved_amount",
        "is_active",
        "sort_order",
        "fund_workspace_link",
    )
    list_filter = ("is_active", "budget__status")
    search_fields = (
        "code",
        "name",
        "description",
        "budget__code",
        "budget__name",
        "budget__fund__code",
    )
    ordering = ("budget__code", "sort_order", "code")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("budget", "budget__fund")

    @admin.display(description="Fund Workspace")
    def fund_workspace_link(self, obj):
        if not obj or not obj.budget.fund_id:
            return "-"
        url = reverse("accounting_admin:accounting-fund-detail", args=[obj.budget.fund_id])
        return format_html('<a href="{}">Open fund</a>', url)

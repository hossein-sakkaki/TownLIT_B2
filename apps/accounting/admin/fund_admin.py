# apps/accounting/admin/fund_admin.py

from django.contrib import admin
from django.core.exceptions import ValidationError

from apps.accounting.models import (
    Fund,
    Budget,
    BudgetLine,
    FundPolicy,
    FundAllowedAccount,
    FundAllowedBudgetLine,
)
from .site import accounting_admin_site


class FundPolicyInline(admin.StackedInline):
    """
    Inline policy for one fund.
    """

    model = FundPolicy
    extra = 0
    max_num = 1
    can_delete = False
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
    """
    Inline allowed accounts for a fund.
    """

    model = FundAllowedAccount
    extra = 0
    autocomplete_fields = ("account",)
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
    """
    Inline allowed budget lines for a fund.
    """

    model = FundAllowedBudgetLine
    extra = 0
    autocomplete_fields = ("budget_line",)
    fields = (
        "budget_line",
        "created_at",
    )
    readonly_fields = ("created_at",)


class BudgetLineInline(admin.TabularInline):
    """
    Inline budget lines.
    """

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
    Admin for funds and grants.
    """

    list_display = (
        "code",
        "name",
        "fund_type",
        "status",
        "is_restricted",
        "total_awarded",
        "currency",
        "start_date",
        "end_date",
        "is_active",
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
    inlines = [
        FundPolicyInline,
        FundAllowedAccountInline,
        FundAllowedBudgetLineInline,
    ]

    @admin.display(description="Reports")
    def fund_reports_link(self, obj):
        return "-"


@admin.register(Budget, site=accounting_admin_site)
class BudgetAdmin(admin.ModelAdmin):
    """
    Admin for budgets.
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
    )
    list_filter = (
        "status",
        "currency",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
        "description",
        "fund__code",
        "fund__name",
    )
    ordering = ("code",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [BudgetLineInline]


@admin.register(BudgetLine, site=accounting_admin_site)
class BudgetLineAdmin(admin.ModelAdmin):
    """
    Read/write admin for budget lines.
    """

    list_display = (
        "budget",
        "code",
        "name",
        "approved_amount",
        "is_active",
        "sort_order",
        "created_at",
    )
    list_filter = (
        "is_active",
        "budget__status",
    )
    search_fields = (
        "code",
        "name",
        "description",
        "budget__code",
        "budget__name",
    )
    ordering = ("budget__code", "sort_order", "code")
    readonly_fields = ("created_at", "updated_at")
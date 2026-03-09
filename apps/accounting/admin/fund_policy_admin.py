# apps/accounting/admin/fund_policy_admin.py

from django.contrib import admin

from apps.accounting.models import FundPolicy
from .site import accounting_admin_site


@admin.register(FundPolicy, site=accounting_admin_site)
class FundPolicyAdmin(admin.ModelAdmin):
    """
    Standalone admin for fund restriction policies.
    """

    list_display = (
        "fund",
        "mode",
        "enforce_rules",
        "enforce_date_window",
        "prevent_budget_overrun",
        "require_budget_line_for_expenses",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "mode",
        "enforce_rules",
        "enforce_date_window",
        "prevent_budget_overrun",
        "require_budget_line_for_expenses",
    )
    search_fields = (
        "fund__code",
        "fund__name",
        "note",
    )
    autocomplete_fields = ("fund",)
    readonly_fields = ("created_at", "updated_at")
# apps/accounting/admin/transaction_admin.py

from django.contrib import admin

from apps.accounting.models import Transaction
from .site import accounting_admin_site


@admin.register(Transaction, site=accounting_admin_site)
class TransactionAdmin(admin.ModelAdmin):
    """
    Read-focused admin for transaction lines.
    Useful for audit and ledger tracing.
    """

    list_display = (
        "journal_entry",
        "line_number",
        "account",
        "debit",
        "credit",
        "fund_code",
        "budget_code",
        "created_at",
    )
    list_filter = (
        "account__account_type",
        "fund_code",
        "budget_code",
        "created_at",
    )
    search_fields = (
        "journal_entry__entry_number",
        "journal_entry__reference",
        "account__code",
        "account__name",
        "memo",
        "fund_code",
        "budget_code",
    )
    ordering = ("-journal_entry__entry_date", "-journal_entry__id", "line_number")
    readonly_fields = (
        "journal_entry",
        "line_number",
        "account",
        "debit",
        "credit",
        "memo",
        "fund_code",
        "budget_code",
        "created_at",
    )
    list_select_related = ("journal_entry", "account")

    def has_add_permission(self, request):
        """
        Block direct add from transaction admin.
        """

        return False

    def has_change_permission(self, request, obj=None):
        """
        Keep transaction audit admin read-only.
        """

        return False

    def has_delete_permission(self, request, obj=None):
        """
        Never allow hard delete.
        """

        return False
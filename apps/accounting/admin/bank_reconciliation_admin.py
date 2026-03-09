# apps/accounting/admin/bank_reconciliation_admin.py

from django.contrib import admin, messages

from apps.accounting.models import (
    BankStatementImport,
    BankStatementLine,
    BankReconciliationSession,
)
from apps.accounting.services.bank_import_service import CSVBankImportService
from apps.accounting.services.bank_reconciliation_service import (
    suggest_match_for_bank_line,
    confirm_match,
    ignore_bank_line,
    refresh_reconciliation_session,
    complete_reconciliation_session,
)
from .site import accounting_admin_site


class BankStatementLineInline(admin.TabularInline):
    """
    Read-focused inline for imported bank lines.
    """

    model = BankStatementLine
    extra = 0
    fields = (
        "transaction_date",
        "posted_date",
        "description",
        "reference",
        "amount",
        "balance_after",
        "external_id",
        "match_status",
        "matched_journal_entry",
        "created_at",
    )
    readonly_fields = fields
    can_delete = False
    show_change_link = True


@admin.register(BankStatementImport, site=accounting_admin_site)
class BankStatementImportAdmin(admin.ModelAdmin):
    """
    Admin for bank statement imports.
    """

    list_display = (
        "id",
        "bank_account",
        "file_name",
        "statement_date",
        "period_start",
        "period_end",
        "opening_balance",
        "closing_balance",
        "status",
        "imported_by",
        "created_at",
    )
    list_filter = (
        "status",
        "bank_account",
        "currency",
        "created_at",
    )
    search_fields = (
        "file_name",
        "bank_account__code",
        "bank_account__name",
        "note",
    )
    raw_id_fields = ("bank_account", "imported_by")
    readonly_fields = ("created_at",)
    inlines = [BankStatementLineInline]
    actions = ["process_csv_import"]

    @admin.action(description="Process selected CSV statement imports")
    def process_csv_import(self, request, queryset):
        """
        Parse CSV files and create statement lines.
        """

        processed = 0
        service = CSVBankImportService()

        for statement_import in queryset:
            try:
                service.import_csv(statement_import=statement_import)
                processed += 1
            except Exception:
                continue

        self.message_user(
            request,
            f"{processed} statement import(s) processed.",
            level=messages.SUCCESS,
        )


@admin.register(BankStatementLine, site=accounting_admin_site)
class BankStatementLineAdmin(admin.ModelAdmin):
    """
    Admin for bank statement lines.
    """

    list_display = (
        "bank_account",
        "transaction_date",
        "description",
        "reference",
        "amount",
        "match_status",
        "matched_journal_entry",
        "matched_by",
        "matched_at",
    )
    list_filter = (
        "bank_account",
        "match_status",
        "transaction_date",
    )
    search_fields = (
        "description",
        "reference",
        "external_id",
        "matched_journal_entry__entry_number",
    )
    raw_id_fields = ("statement_import", "bank_account", "matched_journal_entry", "matched_by")
    readonly_fields = ("created_at",)
    actions = [
        "suggest_matches",
        "ignore_selected_lines",
    ]

    @admin.action(description="Suggest matches for selected bank lines")
    def suggest_matches(self, request, queryset):
        """
        Suggest journal entry matches.
        """

        updated = 0

        for line in queryset.select_related("bank_account", "matched_journal_entry"):
            try:
                match = suggest_match_for_bank_line(bank_line=line)
                if match:
                    updated += 1
            except Exception:
                continue

        self.message_user(
            request,
            f"{updated} bank line(s) received match suggestions.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Ignore selected bank lines")
    def ignore_selected_lines(self, request, queryset):
        """
        Mark selected bank lines as ignored.
        """

        updated = 0

        for line in queryset:
            try:
                ignore_bank_line(
                    bank_line=line,
                    user=request.user,
                    note="Ignored from admin action",
                )
                updated += 1
            except Exception:
                continue

        self.message_user(
            request,
            f"{updated} bank line(s) ignored.",
            level=messages.SUCCESS,
        )

    def save_model(self, request, obj, form, change):
        """
        Confirm match when matched_journal_entry is manually assigned.
        """

        if obj.matched_journal_entry_id and obj.match_status != obj.MATCH_MATCHED:
            confirm_match(
                bank_line=obj,
                journal_entry=obj.matched_journal_entry,
                user=request.user,
            )
            return

        super().save_model(request, obj, form, change)

@admin.register(BankReconciliationSession, site=accounting_admin_site)
class BankReconciliationSessionAdmin(admin.ModelAdmin):
    """
    Admin for bank reconciliation sessions.
    """

    list_display = (
        "bank_account",
        "period_start",
        "period_end",
        "statement_ending_balance",
        "ledger_ending_balance",
        "unreconciled_difference",
        "status",
        "completed_by",
        "completed_at",
        "created_at",
    )
    list_filter = (
        "bank_account",
        "status",
        "period_start",
        "period_end",
    )
    search_fields = (
        "bank_account__code",
        "bank_account__name",
        "note",
    )
    raw_id_fields = ("bank_account", "completed_by")
    readonly_fields = (
        "ledger_ending_balance",
        "unreconciled_difference",
        "created_at",
        "updated_at",
        "completed_at",
    )
    actions = [
        "refresh_selected_sessions",
        "complete_selected_sessions",
    ]

    @admin.action(description="Refresh selected reconciliation sessions")
    def refresh_selected_sessions(self, request, queryset):
        """
        Refresh reconciliation balances.
        """

        updated = 0

        for session in queryset:
            try:
                refresh_reconciliation_session(session=session)
                updated += 1
            except Exception:
                continue

        self.message_user(
            request,
            f"{updated} reconciliation session(s) refreshed.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Complete selected reconciliation sessions")
    def complete_selected_sessions(self, request, queryset):
        """
        Complete reconciliation sessions.
        """

        updated = 0

        for session in queryset:
            try:
                complete_reconciliation_session(
                    session=session,
                    user=request.user,
                )
                updated += 1
            except Exception:
                continue

        self.message_user(
            request,
            f"{updated} reconciliation session(s) completed.",
            level=messages.SUCCESS,
        )
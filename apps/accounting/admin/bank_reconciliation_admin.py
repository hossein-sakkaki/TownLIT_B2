# apps/accounting/admin/bank_reconciliation_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.contrib import admin, messages
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from apps.accounting.models import (
    BankReconciliationSession,
    BankStatementImport,
    BankStatementLine,
)
from apps.accounting.services.bank_import_service import CSVBankImportService
from apps.accounting.services.bank_reconciliation_service import (
    complete_reconciliation_session,
    confirm_match,
    ignore_bank_line,
    lock_reconciliation_session,
    refresh_reconciliation_session,
    suggest_match_for_bank_line,
    unmatch_bank_line,
)

from .site import accounting_admin_site


class BankStatementLineInline(admin.TabularInline):
    """
    Read-only statement lines under the imported statement.
    """

    model = BankStatementLine
    extra = 0
    can_delete = False
    show_change_link = True
    fields = (
        "transaction_date",
        "description",
        "reference",
        "amount",
        "balance_after",
        "match_status",
        "matched_journal_entry",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BankStatementImport, site=accounting_admin_site)
class BankStatementImportAdmin(admin.ModelAdmin):
    """
    Bank CSV intake.

    Accountants upload once, save/process, then review imported lines on the
    same record. Processing remains inside CSVBankImportService.
    """

    change_form_template = "admin/accounting/bank_statement_import/change_form.html"

    list_display = (
        "id",
        "bank_account",
        "file_name",
        "period_start",
        "period_end",
        "status",
        "workflow",
        "line_count",
        "processed_at",
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
        "file_hash",
        "note",
    )
    autocomplete_fields = ("bank_account",)
    readonly_fields = (
        "file_hash",
        "file_dedupe_key",
        "error_message",
        "processed_at",
        "status",
        "created_at",
    )
    inlines = (BankStatementLineInline,)
    actions = ("process_csv_import",)
    list_select_related = ("bank_account", "imported_by")
    ordering = ("-period_end", "-id")
    list_per_page = 40

    fieldsets = (
        (
            "Statement",
            {
                "fields": (
                    "bank_account",
                    "source_file",
                    "file_name",
                    "statement_date",
                    "period_start",
                    "period_end",
                    "opening_balance",
                    "closing_balance",
                    "currency",
                    "status",
                ),
            },
        ),
        (
            "Import Result",
            {
                "fields": (
                    "processed_at",
                    "file_hash",
                    "file_dedupe_key",
                    "error_message",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "imported_by",
                    "note",
                    "created_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Lines")
    def line_count(self, obj):
        return obj.lines.count()

    @admin.display(description="Next step")
    def workflow(self, obj):
        workspace_url = reverse("accounting_admin:accounting-banking-workspace")
        return format_html(
            '<a class="button" href="{}?bank_account={}">Open banking</a>',
            workspace_url,
            obj.bank_account_id,
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))

        if obj:
            readonly.append("imported_by")

        if obj and obj.status != BankStatementImport.STATUS_IMPORTED:
            readonly.extend(
                [
                    "bank_account",
                    "source_file",
                    "file_name",
                    "statement_date",
                    "period_start",
                    "period_end",
                    "opening_balance",
                    "closing_balance",
                    "currency",
                    "status",
                ]
            )

        return tuple(dict.fromkeys(readonly))

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.imported_by_id:
            obj.imported_by = request.user

        if not obj.file_name and obj.source_file:
            obj.file_name = obj.source_file.name.rsplit("/", 1)[-1]

        super().save_model(request, obj, form, change)

    def _process_one(self, request, statement_import):
        try:
            created = CSVBankImportService().import_csv(
                statement_import=statement_import,
            )
            self.message_user(
                request,
                f"{statement_import.file_name or statement_import.id}: "
                f"processed successfully ({created} line(s)).",
                level=messages.SUCCESS,
            )
            return True
        except Exception as exc:
            self.message_user(
                request,
                f"{statement_import.file_name or statement_import.id}: {exc}",
                level=messages.ERROR,
            )
            return False

    @admin.action(description="Process selected bank statements")
    def process_csv_import(self, request, queryset):
        processed = 0

        for statement_import in queryset.order_by("id"):
            if self._process_one(request, statement_import):
                processed += 1

        if not processed:
            self.message_user(
                request,
                "No bank statement imports were processed.",
                level=messages.WARNING,
            )

    def response_add(self, request, obj, post_url_continue=None):
        if "_process_statement" in request.POST:
            self._process_one(request, obj)
            return redirect(
                reverse(
                    "accounting_admin:accounting_bankstatementimport_change",
                    args=[obj.id],
                )
            )

        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if "_process_statement" in request.POST:
            self._process_one(request, obj)
            return redirect(
                reverse(
                    "accounting_admin:accounting_bankstatementimport_change",
                    args=[obj.id],
                )
            )

        return super().response_change(request, obj)


@admin.register(BankStatementLine, site=accounting_admin_site)
class BankStatementLineAdmin(admin.ModelAdmin):
    """
    Imported bank-line review and matching.

    Statement facts are immutable from Admin. Match transitions go through
    reconciliation services.
    """

    list_display = (
        "bank_account",
        "transaction_date",
        "description",
        "reference",
        "amount",
        "match_status",
        "matched_journal_entry",
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
        "fingerprint",
        "matched_journal_entry__entry_number",
    )
    raw_id_fields = ("matched_journal_entry",)
    readonly_fields = (
        "statement_import",
        "bank_account",
        "transaction_date",
        "posted_date",
        "description",
        "reference",
        "amount",
        "balance_after",
        "external_id",
        "fingerprint",
        "external_dedupe_key",
        "match_status",
        "matched_at",
        "matched_by",
        "created_at",
    )
    actions = (
        "suggest_matches",
        "confirm_suggested_matches",
        "ignore_selected_lines",
        "unmatch_selected_lines",
    )
    list_select_related = (
        "bank_account",
        "statement_import",
        "matched_journal_entry",
        "matched_by",
    )
    ordering = ("-transaction_date", "-id")
    list_per_page = 75

    fieldsets = (
        (
            "Bank Transaction",
            {
                "fields": (
                    "statement_import",
                    "bank_account",
                    "transaction_date",
                    "posted_date",
                    "description",
                    "reference",
                    "amount",
                    "balance_after",
                    "external_id",
                ),
            },
        ),
        (
            "Reconciliation",
            {
                "fields": (
                    "match_status",
                    "matched_journal_entry",
                    "matched_by",
                    "matched_at",
                    "note",
                ),
            },
        ),
        (
            "Import Integrity",
            {
                "fields": (
                    "fingerprint",
                    "external_dedupe_key",
                    "created_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def _is_locked_for_reconciliation(self, obj):
        if not obj or not obj.pk:
            return False

        return BankReconciliationSession.objects.filter(
            bank_account=obj.bank_account,
            period_start__lte=obj.transaction_date,
            period_end__gte=obj.transaction_date,
            status__in=(
                BankReconciliationSession.STATUS_COMPLETED,
                BankReconciliationSession.STATUS_LOCKED,
            ),
        ).exists()

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))

        if self._is_locked_for_reconciliation(obj):
            readonly.extend(("matched_journal_entry", "note"))

        return tuple(dict.fromkeys(readonly))

    def save_model(self, request, obj, form, change):
        if not change:
            raise ValueError("Bank statement lines cannot be created manually.")

        original = BankStatementLine.objects.get(pk=obj.pk)
        requested_match_id = obj.matched_journal_entry_id
        requested_note = obj.note

        if requested_match_id != original.matched_journal_entry_id:
            if requested_match_id:
                confirm_match(
                    bank_line=original,
                    journal_entry=obj.matched_journal_entry,
                    user=request.user,
                )
            else:
                unmatch_bank_line(bank_line=original)

            original.refresh_from_db()

        if requested_note != original.note:
            original.note = requested_note
            original.save(update_fields=("note",))

    @admin.action(description="Suggest journal matches")
    def suggest_matches(self, request, queryset):
        updated = 0

        for line in queryset:
            try:
                match = suggest_match_for_bank_line(bank_line=line)
                if match:
                    updated += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Bank line {line.id}: {exc}",
                    level=messages.ERROR,
                )

        if updated:
            self.message_user(
                request,
                f"{updated} bank line(s) received a match suggestion.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Confirm selected suggested matches")
    def confirm_suggested_matches(self, request, queryset):
        updated = 0

        for line in queryset.select_related("matched_journal_entry"):
            if not line.matched_journal_entry_id:
                continue

            try:
                confirm_match(
                    bank_line=line,
                    journal_entry=line.matched_journal_entry,
                    user=request.user,
                )
                updated += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Bank line {line.id}: {exc}",
                    level=messages.ERROR,
                )

        if updated:
            self.message_user(
                request,
                f"{updated} bank line match(es) confirmed.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Ignore selected bank lines")
    def ignore_selected_lines(self, request, queryset):
        updated = 0

        for line in queryset:
            try:
                ignore_bank_line(
                    bank_line=line,
                    user=request.user,
                    note="Ignored from Accounting Admin",
                )
                updated += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Bank line {line.id}: {exc}",
                    level=messages.ERROR,
                )

        if updated:
            self.message_user(
                request,
                f"{updated} bank line(s) ignored.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Unmatch selected bank lines")
    def unmatch_selected_lines(self, request, queryset):
        updated = 0

        for line in queryset:
            try:
                unmatch_bank_line(bank_line=line)
                updated += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Bank line {line.id}: {exc}",
                    level=messages.ERROR,
                )

        if updated:
            self.message_user(
                request,
                f"{updated} bank line(s) unmatched.",
                level=messages.SUCCESS,
            )


@admin.register(BankReconciliationSession, site=accounting_admin_site)
class BankReconciliationSessionAdmin(admin.ModelAdmin):
    """
    Monthly bank reconciliation control.

    Session status transitions are service-controlled. Completed sessions may
    be locked; locked sessions are immutable from Admin.
    """

    list_display = (
        "bank_account",
        "period_start",
        "period_end",
        "statement_ending_balance",
        "ledger_ending_balance",
        "unreconciled_difference",
        "status",
        "completed_at",
        "locked_at",
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
    autocomplete_fields = ("bank_account",)
    readonly_fields = (
        "status",
        "ledger_ending_balance",
        "unreconciled_difference",
        "completed_by",
        "completed_at",
        "locked_by",
        "locked_at",
        "created_at",
        "updated_at",
    )
    actions = (
        "refresh_selected_sessions",
    )
    list_select_related = (
        "bank_account",
        "completed_by",
        "locked_by",
    )
    ordering = ("-period_end", "-id")
    list_per_page = 40

    fieldsets = (
        (
            "Reconciliation",
            {
                "fields": (
                    "bank_account",
                    "period_start",
                    "period_end",
                    "statement_ending_balance",
                    "ledger_ending_balance",
                    "unreconciled_difference",
                    "status",
                    "note",
                ),
            },
        ),
        (
            "Completion / Lock Audit",
            {
                "fields": (
                    "completed_by",
                    "completed_at",
                    "locked_by",
                    "locked_at",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))

        if obj:
            readonly.extend(("bank_account", "period_start", "period_end"))

        if obj and obj.status in (
            BankReconciliationSession.STATUS_COMPLETED,
            BankReconciliationSession.STATUS_LOCKED,
        ):
            readonly.extend(("statement_ending_balance", "note"))

        return tuple(dict.fromkeys(readonly))

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:object_id>/review/",
                self.admin_site.admin_view(self.reconciliation_review_view),
                name="accounting_bankreconciliationsession_review",
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Workflow")
    def review_link(self, obj):
        return format_html(
            '<a class="button" href="{}">Review</a>',
            reverse(
                "accounting_admin:accounting_bankreconciliationsession_review",
                args=[obj.id],
            ),
        )

    def response_add(self, request, obj, post_url_continue=None):
        if "_start_review" in request.POST:
            return redirect(
                reverse(
                    "accounting_admin:accounting_bankreconciliationsession_review",
                    args=[obj.id],
                )
            )
        return super().response_add(request, obj, post_url_continue)

    def reconciliation_review_view(self, request, object_id):
        session = self.get_object(request, object_id)
        if session is None:
            raise Http404("Reconciliation session not found.")

        review_url = reverse(
            "accounting_admin:accounting_bankreconciliationsession_review",
            args=[session.id],
        )

        if request.method == "POST":
            action = (request.POST.get("workflow_action") or "").strip()

            try:
                if action in {"suggest", "confirm", "ignore", "unmatch"}:
                    line_id = request.POST.get("line_id")
                    line = BankStatementLine.objects.select_related(
                        "matched_journal_entry",
                        "bank_account",
                    ).get(
                        id=line_id,
                        bank_account=session.bank_account,
                        transaction_date__gte=session.period_start,
                        transaction_date__lte=session.period_end,
                    )

                    if action == "suggest":
                        match = suggest_match_for_bank_line(bank_line=line)
                        if match:
                            messages.success(
                                request,
                                f"Suggested {match.entry_number} for bank line {line.id}.",
                            )
                        else:
                            messages.warning(
                                request,
                                f"No unique ledger match was found for bank line {line.id}.",
                            )

                    elif action == "confirm":
                        if not line.matched_journal_entry_id:
                            raise ValueError(
                                "This bank line has no suggested journal entry to confirm."
                            )
                        confirm_match(
                            bank_line=line,
                            journal_entry=line.matched_journal_entry,
                            user=request.user,
                        )
                        messages.success(
                            request,
                            f"Bank line {line.id} match confirmed.",
                        )

                    elif action == "ignore":
                        ignore_bank_line(
                            bank_line=line,
                            user=request.user,
                            note="Reviewed and ignored from reconciliation workspace",
                        )
                        messages.success(
                            request,
                            f"Bank line {line.id} marked as ignored.",
                        )

                    elif action == "unmatch":
                        unmatch_bank_line(bank_line=line)
                        messages.success(
                            request,
                            f"Bank line {line.id} returned to unmatched.",
                        )

                elif action == "refresh":
                    refresh_reconciliation_session(session=session)
                    messages.success(request, "Reconciliation balances refreshed.")

                elif action == "complete":
                    complete_reconciliation_session(
                        session=session,
                        user=request.user,
                    )
                    messages.success(request, "Reconciliation completed successfully.")

                elif action == "lock":
                    lock_reconciliation_session(
                        session=session,
                        user=request.user,
                    )
                    messages.success(request, "Reconciliation locked successfully.")

                else:
                    messages.error(request, "Unknown reconciliation action.")

            except Exception as exc:
                messages.error(request, str(exc))

            return redirect(review_url)

        session.refresh_from_db()

        lines = list(
            BankStatementLine.objects.select_related(
                "statement_import",
                "matched_journal_entry",
                "matched_by",
            )
            .filter(
                bank_account=session.bank_account,
                transaction_date__gte=session.period_start,
                transaction_date__lte=session.period_end,
            )
            .order_by("transaction_date", "id")
        )

        line_counts = {
            "total": len(lines),
            "unmatched": sum(
                1 for line in lines if line.match_status == BankStatementLine.MATCH_UNMATCHED
            ),
            "suggested": sum(
                1 for line in lines if line.match_status == BankStatementLine.MATCH_SUGGESTED
            ),
            "matched": sum(
                1 for line in lines if line.match_status == BankStatementLine.MATCH_MATCHED
            ),
            "ignored": sum(
                1 for line in lines if line.match_status == BankStatementLine.MATCH_IGNORED
            ),
        }

        imports = list(
            BankStatementImport.objects.filter(
                bank_account=session.bank_account,
                period_start__lte=session.period_end,
                period_end__gte=session.period_start,
            ).order_by("period_start", "id")
        )

        line_rows = [
            {
                "line": line,
                "change_url": reverse(
                    "accounting_admin:accounting_bankstatementline_change",
                    args=[line.id],
                ),
            }
            for line in lines
        ]

        context = {
            **self.admin_site.each_context(request),
            "title": (
                f"Reconcile {session.bank_account.name} — "
                f"{session.period_start} to {session.period_end}"
            ),
            "opts": self.model._meta,
            "session": session,
            "line_rows": line_rows,
            "line_counts": line_counts,
            "statement_imports": imports,
            "review_url": review_url,
            "change_url": reverse(
                "accounting_admin:accounting_bankreconciliationsession_change",
                args=[session.id],
            ),
            "banking_workspace_url": (
                f'{reverse("accounting_admin:accounting-banking-workspace")}'
                f'?bank_account={session.bank_account_id}'
            ),
            "can_edit_lines": session.status == BankReconciliationSession.STATUS_OPEN,
            "can_complete": session.status == BankReconciliationSession.STATUS_OPEN,
            "can_lock": session.status == BankReconciliationSession.STATUS_COMPLETED,
            "is_locked": session.status == BankReconciliationSession.STATUS_LOCKED,
        }

        return TemplateResponse(
            request,
            "admin/accounting/banking/reconciliation_review.html",
            context,
        )

    @admin.action(description="Refresh selected reconciliations")
    def refresh_selected_sessions(self, request, queryset):
        updated = 0

        for session in queryset:
            try:
                refresh_reconciliation_session(session=session)
                updated += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Reconciliation {session.id}: {exc}",
                    level=messages.ERROR,
                )

        if updated:
            self.message_user(
                request,
                f"{updated} reconciliation session(s) refreshed.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Complete selected reconciliations")
    def complete_selected_sessions(self, request, queryset):
        updated = 0

        for session in queryset:
            try:
                complete_reconciliation_session(
                    session=session,
                    user=request.user,
                )
                updated += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Reconciliation {session.id}: {exc}",
                    level=messages.ERROR,
                )

        if updated:
            self.message_user(
                request,
                f"{updated} reconciliation session(s) completed.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Lock selected completed reconciliations")
    def lock_selected_sessions(self, request, queryset):
        updated = 0

        for session in queryset:
            try:
                lock_reconciliation_session(
                    session=session,
                    user=request.user,
                )
                updated += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Reconciliation {session.id}: {exc}",
                    level=messages.ERROR,
                )

        if updated:
            self.message_user(
                request,
                f"{updated} reconciliation session(s) locked.",
                level=messages.SUCCESS,
            )

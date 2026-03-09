# apps/accounting/admin/workflow_admin.py

from django.contrib import admin, messages

from apps.accounting.models import AccountingApproval, JournalEntry
from apps.accounting.services.workflow_service import (
    submit_for_approval,
    approve_entry,
    reject_entry,
)
from .site import accounting_admin_site


@admin.register(AccountingApproval, site=accounting_admin_site)
class AccountingApprovalAdmin(admin.ModelAdmin):
    """
    Admin for accounting workflow approvals.
    """

    list_display = (
        "journal_entry",
        "status",
        "submitted_by",
        "submitted_at",
        "approved_by",
        "approved_at",
        "rejected_by",
        "rejected_at",
    )
    list_filter = (
        "status",
        "submitted_at",
        "approved_at",
        "rejected_at",
    )
    search_fields = (
        "journal_entry__entry_number",
        "journal_entry__reference",
        "rejection_reason",
        "note",
    )
    raw_id_fields = (
        "journal_entry",
        "submitted_by",
        "approved_by",
        "rejected_by",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    actions = [
        "submit_selected",
        "approve_selected",
    ]

    @admin.action(description="Submit selected entries for approval")
    def submit_selected(self, request, queryset):
        """
        Submit workflows to approval state.
        """

        updated = 0

        for workflow in queryset.select_related("journal_entry"):
            try:
                submit_for_approval(
                    journal_entry=workflow.journal_entry,
                    user=request.user,
                )
                updated += 1
            except Exception:
                continue

        self.message_user(
            request,
            f"{updated} workflow(s) submitted.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Approve selected submitted entries")
    def approve_selected(self, request, queryset):
        """
        Approve workflows.
        """

        updated = 0

        for workflow in queryset.select_related("journal_entry"):
            try:
                approve_entry(
                    journal_entry=workflow.journal_entry,
                    user=request.user,
                )
                updated += 1
            except Exception:
                continue

        self.message_user(
            request,
            f"{updated} workflow(s) approved.",
            level=messages.SUCCESS,
        )
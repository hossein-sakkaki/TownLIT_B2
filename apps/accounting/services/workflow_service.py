# apps/accounting/services/workflow_service.py

from django.utils import timezone

from apps.accounting.models import AccountingApproval, JournalEntry


class AccountingWorkflowError(Exception):
    """Raised when workflow transition is invalid."""
    pass


def ensure_workflow(journal_entry: JournalEntry) -> AccountingApproval:
    """
    Ensure workflow object exists for the journal entry.
    """

    workflow, _ = AccountingApproval.objects.get_or_create(
        journal_entry=journal_entry,
        defaults={"status": AccountingApproval.STATUS_DRAFT},
    )
    return workflow


def submit_for_approval(*, journal_entry: JournalEntry, user) -> AccountingApproval:
    """
    Move draft entry to submitted state.
    """

    workflow = ensure_workflow(journal_entry)

    if workflow.status not in {
        AccountingApproval.STATUS_DRAFT,
        AccountingApproval.STATUS_REJECTED,
    }:
        raise AccountingWorkflowError("Only draft or rejected entries can be submitted.")

    workflow.status = AccountingApproval.STATUS_SUBMITTED
    workflow.submitted_by = user
    workflow.submitted_at = timezone.now()
    workflow.rejection_reason = ""
    workflow.save(
        update_fields=[
            "status",
            "submitted_by",
            "submitted_at",
            "rejection_reason",
            "updated_at",
        ]
    )
    return workflow


def approve_entry(*, journal_entry: JournalEntry, user) -> AccountingApproval:
    """
    Approve a submitted entry.
    """

    workflow = ensure_workflow(journal_entry)

    if workflow.status != AccountingApproval.STATUS_SUBMITTED:
        raise AccountingWorkflowError("Only submitted entries can be approved.")

    workflow.status = AccountingApproval.STATUS_APPROVED
    workflow.approved_by = user
    workflow.approved_at = timezone.now()
    workflow.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "updated_at",
        ]
    )
    return workflow


def reject_entry(*, journal_entry: JournalEntry, user, reason: str) -> AccountingApproval:
    """
    Reject a submitted entry.
    """

    workflow = ensure_workflow(journal_entry)

    if workflow.status != AccountingApproval.STATUS_SUBMITTED:
        raise AccountingWorkflowError("Only submitted entries can be rejected.")

    workflow.status = AccountingApproval.STATUS_REJECTED
    workflow.rejected_by = user
    workflow.rejected_at = timezone.now()
    workflow.rejection_reason = reason.strip()
    workflow.save(
        update_fields=[
            "status",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "updated_at",
        ]
    )
    return workflow


def mark_posted(*, journal_entry: JournalEntry) -> AccountingApproval:
    """
    Mark workflow as posted once journal entry is posted.
    """

    workflow = ensure_workflow(journal_entry)
    workflow.status = AccountingApproval.STATUS_POSTED
    workflow.save(update_fields=["status", "updated_at"])
    return workflow
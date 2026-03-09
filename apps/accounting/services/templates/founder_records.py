# apps/accounting/services/templates/founder_records.py

from apps.accounting.models import FounderLoan
from .founder import record_founder_loan


def create_founder_loan_record(
    *,
    lender,
    lender_display_name: str,
    entry_date,
    amount,
    expense_account_code: str,
    description: str,
    reference: str = "",
    source_ref: str = "",
    created_by=None,
    approved_by=None,
):
    """
    Create founder loan domain record and linked journal entry.
    """

    entry = record_founder_loan(
        entry_date=entry_date,
        amount=amount,
        expense_account_code=expense_account_code,
        description=description,
        reference=reference,
        source_ref=source_ref,
        created_by=created_by,
        approved_by=approved_by,
    )

    return FounderLoan.objects.create(
        lender=lender,
        lender_display_name=lender_display_name,
        principal_amount=amount,
        loan_date=entry_date,
        description=description,
        journal_entry=entry,
    )
# apps/accounting/services/templates/founder_records.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from decimal import Decimal

from django.db import transaction as db_transaction

from apps.accounting.models import FounderLoan

from .founder import (
    record_founder_loan,
    record_founder_repayment,
)


ZERO = Decimal("0.00")
CENT = Decimal("0.01")


class FounderLoanWorkflowError(Exception):
    """Raised when founder-loan workflow fails."""

    pass


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
    """Create founder-loan record and linked ledger entry."""

    amount = _money(amount)

    if amount <= ZERO:
        raise FounderLoanWorkflowError(
            "Founder loan amount must be greater than zero."
        )

    with db_transaction.atomic():
        loan = FounderLoan.objects.create(
            lender=lender,
            lender_display_name=lender_display_name,
            principal_amount=amount,
            loan_date=entry_date,
            description=description,
        )

        effective_source_ref = (
            source_ref.strip()
            or f"founder_loan:{loan.id}"
        )

        entry = record_founder_loan(
            entry_date=entry_date,
            amount=amount,
            expense_account_code=expense_account_code,
            description=description,
            reference=reference,
            source_ref=effective_source_ref,
            created_by=created_by,
            approved_by=approved_by,
        )

        loan.journal_entry = entry
        loan.save(
            update_fields=[
                "journal_entry",
                "updated_at",
            ]
        )

        return loan


def repay_founder_loan_record(
    *,
    founder_loan: FounderLoan,
    entry_date,
    amount,
    repayment_ref: str,
    description: str,
    reference: str = "",
    bank_account_code: str = "1010",
    created_by=None,
    approved_by=None,
):
    """Repay founder loan and sync business state."""

    amount = _money(amount)
    repayment_ref = (
        repayment_ref or ""
    ).strip()

    if amount <= ZERO:
        raise FounderLoanWorkflowError(
            "Repayment amount must be greater than zero."
        )

    if not repayment_ref:
        raise FounderLoanWorkflowError(
            "repayment_ref is required for idempotency."
        )

    with db_transaction.atomic():
        loan = (
            FounderLoan.objects
            .select_for_update()
            .get(pk=founder_loan.pk)
        )

        if loan.status == FounderLoan.STATUS_CANCELLED:
            raise FounderLoanWorkflowError(
                "Cancelled founder loans cannot be repaid."
            )

        if loan.status == FounderLoan.STATUS_REPAID:
            raise FounderLoanWorkflowError(
                "This founder loan is already fully repaid."
            )

        outstanding = loan.outstanding_amount

        if amount > outstanding:
            raise FounderLoanWorkflowError(
                f"Repayment cannot exceed outstanding "
                f"amount ({outstanding})."
            )

        source_ref = (
            f"founder_loan:{loan.id}:"
            f"repayment:{repayment_ref}"
        )

        entry = record_founder_repayment(
            entry_date=entry_date,
            amount=amount,
            description=description,
            reference=reference,
            source_ref=source_ref,
            bank_account_code=bank_account_code,
            created_by=created_by,
            approved_by=approved_by,
        )

        loan.repaid_amount = (
            loan.repaid_amount
            + amount
        ).quantize(CENT)

        if loan.repaid_amount == loan.principal_amount:
            loan.status = FounderLoan.STATUS_REPAID
        else:
            loan.status = FounderLoan.STATUS_PARTIAL

        loan.save(
            update_fields=[
                "repaid_amount",
                "status",
                "updated_at",
            ]
        )

        return loan, entry


def _money(value) -> Decimal:
    """Normalize money."""

    return Decimal(
        str(value)
    ).quantize(CENT)
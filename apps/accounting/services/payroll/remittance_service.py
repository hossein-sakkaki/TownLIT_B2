# apps/accounting/services/payroll/remittance_service.py

from decimal import Decimal

from django.db import transaction as db_transaction

from apps.accounting.models import PayRun, PayrollRemittance
from apps.accounting.services.account_lookup import AccountCodes
from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import JournalEntryInput, JournalLineInput
from apps.accounting.services.payroll.remittance_due_date import (
    PayrollRemitterType,
    calculate_remittance_due_date,
)

ZERO = Decimal("0.00")


class PayrollRemittanceError(Exception):
    """
    Raised when payroll remittance fails.
    """
    pass


class PayrollRemittanceService:
    """
    Creates and posts CRA payroll remittances.
    """

    def create_for_pay_run(
        self,
        *,
        pay_run: PayRun,
        due_date=None,
        remitter_type: str = PayrollRemitterType.REGULAR_MONTHLY,
    ) -> PayrollRemittance:
        """
        Create or refresh remittance record from pay run totals.
        """

        stubs = list(pay_run.pay_stubs.all())

        if not stubs:
            raise PayrollRemittanceError("Pay run has no pay stubs.")

        if due_date is None:
            due_date = calculate_remittance_due_date(
                pay_date=pay_run.pay_period.pay_date,
                remitter_type=remitter_type,
            )

        totals = {
            "employee_cpp": ZERO,
            "employer_cpp": ZERO,
            "employee_cpp2": ZERO,
            "employer_cpp2": ZERO,
            "employee_ei": ZERO,
            "employer_ei": ZERO,
            "federal_income_tax": ZERO,
            "provincial_income_tax": ZERO,
        }

        for stub in stubs:
            for key in totals:
                totals[key] += getattr(stub, key) or ZERO

        total_due = sum(totals.values(), ZERO)

        with db_transaction.atomic():
            existing = (
                PayrollRemittance.objects.select_for_update()
                .filter(pay_run=pay_run)
                .first()
            )

            if existing and existing.status == PayrollRemittance.STATUS_PAID:
                raise PayrollRemittanceError(
                    "This payroll remittance has already been paid and cannot be refreshed."
                )

            if existing and existing.journal_entry_id:
                raise PayrollRemittanceError(
                    "This payroll remittance already has a journal entry and cannot be refreshed."
                )

            remittance, _ = PayrollRemittance.objects.update_or_create(
                pay_run=pay_run,
                defaults={
                    "due_date": due_date,
                    **totals,
                    "total_due": total_due,
                    "status": PayrollRemittance.STATUS_READY,
                },
            )

            return remittance

    def post_payment(
        self,
        *,
        remittance: PayrollRemittance,
        paid_on,
        payment_reference: str,
        bank_account_code: str = AccountCodes.BANK,
        created_by=None,
        approved_by=None,
    ):
        """
        Post actual CRA payroll remittance payment once.
        """

        with db_transaction.atomic():
            locked_remittance = (
                PayrollRemittance.objects.select_for_update()
                .select_related("pay_run")
                .get(id=remittance.id)
            )

            if locked_remittance.status == PayrollRemittance.STATUS_PAID:
                raise PayrollRemittanceError(
                    "This remittance has already been marked as paid."
                )

            if locked_remittance.journal_entry_id:
                raise PayrollRemittanceError(
                    "This remittance already has a payment journal entry."
                )

            if locked_remittance.status not in {
                PayrollRemittance.STATUS_READY,
                PayrollRemittance.STATUS_DRAFT,
            }:
                raise PayrollRemittanceError(
                    "Only draft or ready remittances can be paid."
                )

            if locked_remittance.total_due <= ZERO:
                raise PayrollRemittanceError(
                    "Remittance total_due must be greater than zero."
                )

            if not payment_reference or not payment_reference.strip():
                raise PayrollRemittanceError(
                    "Payment reference is required for CRA remittance payment."
                )

            lines = []

            self._add_debit(
                lines,
                AccountCodes.CPP_PAYABLE,
                locked_remittance.employee_cpp + locked_remittance.employer_cpp,
                "CPP remittance",
            )

            self._add_debit(
                lines,
                AccountCodes.CPP2_PAYABLE,
                locked_remittance.employee_cpp2 + locked_remittance.employer_cpp2,
                "CPP2 remittance",
            )

            self._add_debit(
                lines,
                AccountCodes.EI_PAYABLE,
                locked_remittance.employee_ei + locked_remittance.employer_ei,
                "EI remittance",
            )

            self._add_debit(
                lines,
                AccountCodes.INCOME_TAX_PAYABLE,
                locked_remittance.federal_income_tax
                + locked_remittance.provincial_income_tax,
                "Income tax remittance",
            )

            if not lines:
                raise PayrollRemittanceError(
                    "No payable remittance lines were found."
                )

            lines.append(
                JournalLineInput(
                    account_code=bank_account_code,
                    debit=ZERO,
                    credit=locked_remittance.total_due,
                    memo=payment_reference.strip(),
                    line_number=len(lines) + 1,
                )
            )

            payload = JournalEntryInput(
                entry_date=paid_on,
                description=(
                    f"Payroll remittance payment - "
                    f"{locked_remittance.pay_run.run_number}"
                ),
                reference=payment_reference.strip(),
                source_app="accounting",
                source_model="payroll_remittance",
                source_ref=f"payroll_remittance_payment:{locked_remittance.id}",
                lines=lines,
                created_by=created_by,
                approved_by=approved_by,
            )

            journal_entry = post_journal_entry(payload)

            locked_remittance.status = PayrollRemittance.STATUS_PAID
            locked_remittance.total_paid = locked_remittance.total_due
            locked_remittance.paid_on = paid_on
            locked_remittance.payment_reference = payment_reference.strip()
            locked_remittance.journal_entry = journal_entry
            locked_remittance.save(
                update_fields=[
                    "status",
                    "total_paid",
                    "paid_on",
                    "payment_reference",
                    "journal_entry",
                    "updated_at",
                ]
            )

            return journal_entry

    def _add_debit(self, lines, account_code, amount, memo):
        """
        Add debit line when amount is positive.
        """

        amount = Decimal(str(amount or ZERO)).quantize(Decimal("0.01"))

        if amount > ZERO:
            lines.append(
                JournalLineInput(
                    account_code=account_code,
                    debit=amount,
                    credit=ZERO,
                    memo=memo,
                    line_number=len(lines) + 1,
                )
            )
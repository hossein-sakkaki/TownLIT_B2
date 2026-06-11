# apps/accounting/services/payroll/posting_service.py

from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction

from apps.accounting.models import PayStub, PayrollSalaryPayment, PayRun
from apps.accounting.services.account_lookup import AccountCodes
from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import JournalEntryInput, JournalLineInput
from django.db import models



ZERO = Decimal("0.00")


class PayrollPostingError(Exception):
    """
    Raised when payroll posting fails.
    """
    pass


class PayrollPostingService:
    """
    Posts payroll pay runs to the general ledger.
    """

    def post_pay_run(self, *, pay_run: PayRun, created_by=None, approved_by=None):
        """
        Post payroll accrual entry for a pay run.

        Supports:
        - Regular payroll accrual
        - Vacation pay accrual
        - Standalone vacation pay payout from accrued vacation payable
        """

        if pay_run.status not in {PayRun.STATUS_CALCULATED, PayRun.STATUS_APPROVED}:
            raise PayrollPostingError("Only calculated or approved pay runs can be posted.")

        stubs = list(pay_run.pay_stubs.select_related("employee"))

        if not stubs:
            raise PayrollPostingError("Pay run has no pay stubs.")

        totals = self._build_totals(stubs)

        lines = []

        # ------------------------------------------------------------
        # Earnings / expense side
        # ------------------------------------------------------------

        self._add_debit(
            lines,
            AccountCodes.SALARIES_AND_WAGES,
            totals["gross_salary"],
            "Gross salary",
        )

        self._add_debit(
            lines,
            AccountCodes.SICK_PAY_EXPENSE,
            totals["sick_pay_paid"],
            "Sick pay paid",
        )

        # Vacation pay has two different meanings:
        # 1) vacation_pay_earned = new accrual expense for this period
        # 2) vacation_pay_paid = payout of previously accrued balance
        #
        # For regular payroll, vacation_pay_earned creates expense and payable.
        # For standalone vacation payout, vacation_pay_paid reduces the payable.
        vacation_pay_earned = totals["vacation_pay_earned"]
        vacation_pay_paid = totals["vacation_pay_paid"]

        if vacation_pay_earned > ZERO:
            self._add_debit(
                lines,
                AccountCodes.VACATION_PAY_EXPENSE,
                vacation_pay_earned,
                "Vacation pay earned",
            )

        if vacation_pay_paid > ZERO:
            self._add_debit(
                lines,
                AccountCodes.VACATION_PAY_PAYABLE,
                vacation_pay_paid,
                "Vacation pay paid from accrued balance",
            )

        self._add_debit(
            lines,
            AccountCodes.EMPLOYER_CPP_EXPENSE,
            totals["employer_cpp"],
            "Employer CPP",
        )

        self._add_debit(
            lines,
            AccountCodes.EMPLOYER_CPP2_EXPENSE,
            totals["employer_cpp2"],
            "Employer CPP2",
        )

        self._add_debit(
            lines,
            AccountCodes.EMPLOYER_EI_EXPENSE,
            totals["employer_ei"],
            "Employer EI",
        )

        # ------------------------------------------------------------
        # Payable / liability side
        # ------------------------------------------------------------

        self._add_credit(
            lines,
            AccountCodes.SALARIES_PAYABLE,
            totals["net_pay"],
            "Net payroll payable",
        )

        self._add_credit(
            lines,
            AccountCodes.CPP_PAYABLE,
            totals["employee_cpp"] + totals["employer_cpp"],
            "CPP payable",
        )

        self._add_credit(
            lines,
            AccountCodes.CPP2_PAYABLE,
            totals["employee_cpp2"] + totals["employer_cpp2"],
            "CPP2 payable",
        )

        self._add_credit(
            lines,
            AccountCodes.EI_PAYABLE,
            totals["employee_ei"] + totals["employer_ei"],
            "EI payable",
        )

        self._add_credit(
            lines,
            AccountCodes.INCOME_TAX_PAYABLE,
            totals["federal_income_tax"] + totals["provincial_income_tax"],
            "Income tax payable",
        )

        # Only newly earned but unpaid vacation pay should increase vacation payable.
        # A standalone vacation payout should NOT create new vacation payable.
        accrued_vacation_not_paid = vacation_pay_earned - vacation_pay_paid

        if accrued_vacation_not_paid > ZERO:
            self._add_credit(
                lines,
                AccountCodes.VACATION_PAY_PAYABLE,
                accrued_vacation_not_paid,
                "Vacation pay payable",
            )

        if not lines:
            raise PayrollPostingError("No payroll posting lines were generated.")

        payload = JournalEntryInput(
            # Accrue payroll expense in the period when the work/pay was earned.
            entry_date=pay_run.pay_period.end_date,
            description=f"Payroll accrual - {pay_run.run_number}",
            reference=pay_run.run_number,
            source_app="accounting",
            source_model="pay_run",
            source_ref=str(pay_run.id),
            lines=lines,
            created_by=created_by,
            approved_by=approved_by,
        )

        with db_transaction.atomic():
            journal_entry = post_journal_entry(payload)

            pay_run.journal_entry = journal_entry
            pay_run.status = PayRun.STATUS_POSTED
            pay_run.posted_at = timezone.now()
            pay_run.save(
                update_fields=[
                    "journal_entry",
                    "status",
                    "posted_at",
                    "updated_at",
                ]
            )

            for stub in stubs:
                stub.journal_entry = journal_entry
                stub.save(update_fields=["journal_entry", "updated_at"])

        return journal_entry

    def post_salary_payment(
        self,
        *,
        pay_stub: PayStub,
        paid_on,
        bank_account_code: str = AccountCodes.BANK,
        payment_reference: str = "",
        payment_method: str = "e_transfer",
        payment_amount: Decimal | None = None,
        created_by=None,
        approved_by=None,
    ):
        """
        Post an actual full or partial salary payment.
        """

        net_pay = pay_stub.net_pay or ZERO
        already_paid = pay_stub.actual_paid or ZERO
        remaining_payable = max(net_pay - already_paid, ZERO)

        if remaining_payable <= ZERO:
            raise PayrollPostingError("This pay stub is already fully paid.")

        amount = Decimal(str(payment_amount if payment_amount is not None else remaining_payable))
        amount = amount.quantize(Decimal("0.01"))

        if amount <= ZERO:
            raise PayrollPostingError("Payment amount must be greater than zero.")

        if amount > remaining_payable:
            raise PayrollPostingError(
                f"Payment amount cannot exceed remaining payable amount ({remaining_payable})."
            )

        reference = payment_reference or pay_stub.payment_note or f"Payroll payment - {pay_stub.pay_run.run_number}"

        payload = JournalEntryInput(
            entry_date=paid_on,
            description=f"Salary payment - {pay_stub.employee.display_name} - {pay_stub.pay_run.run_number}",
            reference=reference,
            source_app="accounting",
            source_model="payroll_salary_payment",
            source_ref=f"{pay_stub.id}-{paid_on}-{amount}",
            lines=[
                JournalLineInput(
                    account_code=AccountCodes.SALARIES_PAYABLE,
                    debit=amount,
                    credit=ZERO,
                    memo=f"Salary payment to {pay_stub.employee.display_name}",
                    line_number=1,
                ),
                JournalLineInput(
                    account_code=bank_account_code,
                    debit=ZERO,
                    credit=amount,
                    memo=reference,
                    line_number=2,
                ),
            ],
            created_by=created_by,
            approved_by=approved_by,
        )

        with db_transaction.atomic():
            journal_entry = post_journal_entry(payload)

            payment = PayrollSalaryPayment.objects.create(
                pay_stub=pay_stub,
                paid_on=paid_on,
                amount=amount,
                payment_method=payment_method,
                payment_reference=reference,
                journal_entry=journal_entry,
                created_by=created_by,
            )

            self._refresh_pay_stub_payment_summary(pay_stub=pay_stub)

            self._refresh_pay_run_payment_status(pay_run=pay_stub.pay_run)

        return payment

    def _refresh_pay_stub_payment_summary(self, *, pay_stub: PayStub) -> PayStub:
        """
        Refresh pay stub payment summary from salary payment records.
        """

        total_paid = (
            pay_stub.salary_payments.aggregate(total=models.Sum("amount"))["total"]
            or ZERO
        )

        latest_payment = pay_stub.salary_payments.order_by("-paid_on", "-id").first()

        pay_stub.actual_paid = total_paid
        pay_stub.salary_payment_amount = total_paid
        pay_stub.net_salary_payable = max((pay_stub.net_pay or ZERO) - total_paid, ZERO)

        if latest_payment:
            pay_stub.salary_paid_on = latest_payment.paid_on
            pay_stub.salary_payment_method = latest_payment.payment_method
            pay_stub.salary_payment_reference = latest_payment.payment_reference
            pay_stub.salary_payment_journal_entry = latest_payment.journal_entry

        pay_stub.save(
            update_fields=[
                "actual_paid",
                "salary_payment_amount",
                "net_salary_payable",
                "salary_paid_on",
                "salary_payment_method",
                "salary_payment_reference",
                "salary_payment_journal_entry",
                "updated_at",
            ]
        )

        return pay_stub

    def _refresh_pay_run_payment_status(self, *, pay_run: PayRun) -> PayRun:
        """
        Refresh pay run totals and paid status after salary payments.
        """

        total_actual_paid = ZERO
        total_salary_payable = ZERO

        for stub in pay_run.pay_stubs.all():
            total_actual_paid += stub.actual_paid or ZERO
            total_salary_payable += stub.net_salary_payable or ZERO

        pay_run.total_actual_paid = total_actual_paid
        pay_run.total_salary_payable = total_salary_payable

        if total_salary_payable <= ZERO and total_actual_paid > ZERO:
            pay_run.status = PayRun.STATUS_PAID

        pay_run.save(
            update_fields=[
                "total_actual_paid",
                "total_salary_payable",
                "status",
                "updated_at",
            ]
        )

        return pay_run

    def _build_totals(self, stubs: list[PayStub]) -> dict[str, Decimal]:
        """
        Aggregate pay stub totals.
        """

        keys = [
            "gross_salary",
            "vacation_pay_earned",
            "vacation_pay_paid",
            "sick_pay_paid",
            "employee_cpp",
            "employee_cpp2",
            "employee_ei",
            "federal_income_tax",
            "provincial_income_tax",
            "employer_cpp",
            "employer_cpp2",
            "employer_ei",
            "net_pay",
        ]

        totals = {key: ZERO for key in keys}

        for stub in stubs:
            for key in keys:
                totals[key] += getattr(stub, key) or ZERO

        return totals

    def _add_debit(self, lines, account_code, amount, memo):
        """
        Add debit line when amount is positive.
        """

        if amount and amount > ZERO:
            lines.append(
                JournalLineInput(
                    account_code=account_code,
                    debit=amount,
                    credit=ZERO,
                    memo=memo,
                    line_number=len(lines) + 1,
                )
            )

    def _add_credit(self, lines, account_code, amount, memo):
        """
        Add credit line when amount is positive.
        """

        if amount and amount > ZERO:
            lines.append(
                JournalLineInput(
                    account_code=account_code,
                    debit=ZERO,
                    credit=amount,
                    memo=memo,
                    line_number=len(lines) + 1,
                )
            )
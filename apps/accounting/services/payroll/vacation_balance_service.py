# apps/accounting/services/payroll/vacation_balance_service.py

from decimal import Decimal
from django.db.models import Sum
from apps.accounting.models import PayrollEmployee, PayStub, PayRun


ZERO = Decimal("0.00")


class VacationPayBalanceService:
    """
    Calculates earned, paid/reserved, and available vacation pay.
    """

    ACTIVE_RUN_STATUSES = [
        PayRun.STATUS_DRAFT,
        PayRun.STATUS_CALCULATED,
        PayRun.STATUS_APPROVED,
        PayRun.STATUS_POSTED,
        PayRun.STATUS_PAID,
    ]

    def get_balance(self, *, employee: PayrollEmployee, tax_year: int | None = None) -> dict:
        """
        Return vacation pay balance.

        Any vacation_pay_paid in a non-void pay run is treated as already
        paid/reserved, even if the bank payment is not recorded yet.
        """

        qs = PayStub.objects.filter(
            employee=employee,
            pay_run__status__in=self.ACTIVE_RUN_STATUSES,
        )

        if tax_year:
            qs = qs.filter(pay_run__pay_period__tax_year=tax_year)

        earned = qs.aggregate(total=Sum("vacation_pay_earned"))["total"] or ZERO
        paid_or_reserved = qs.aggregate(total=Sum("vacation_pay_paid"))["total"] or ZERO

        balance = earned - paid_or_reserved
        if balance < ZERO:
            balance = ZERO

        return {
            "earned": earned,
            "paid": paid_or_reserved,
            "balance": balance,
        }

    def has_vacation_pay_run_for_period(self, *, employee: PayrollEmployee, pay_period) -> bool:
        """
        Prevent duplicate vacation pay runs for the same employee/pay period.
        """

        return PayStub.objects.filter(
            employee=employee,
            pay_run__pay_period=pay_period,
            pay_run__status__in=self.ACTIVE_RUN_STATUSES,
            vacation_pay_paid__gt=ZERO,
        ).exists()

    def get_existing_vacation_pay_run_for_period(self, *, employee: PayrollEmployee, pay_period):
        """
        Return existing vacation pay run for display/warning.
        """

        stub = (
            PayStub.objects.select_related("pay_run")
            .filter(
                employee=employee,
                pay_run__pay_period=pay_period,
                pay_run__status__in=self.ACTIVE_RUN_STATUSES,
                vacation_pay_paid__gt=ZERO,
            )
            .order_by("-id")
            .first()
        )

        return stub.pay_run if stub else None
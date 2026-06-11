# apps/accounting/services/payroll/payroll_type_service.py

from decimal import Decimal

from apps.accounting.models import PayRun, PayStub


ZERO = Decimal("0.00")


def is_vacation_pay_stub(*, pay_stub: PayStub) -> bool:
    """
    Detect standalone vacation pay stub.
    """

    return (
        (pay_stub.vacation_pay_paid or ZERO) > ZERO
        and (pay_stub.gross_salary or ZERO) <= ZERO
    )


def is_vacation_pay_run(*, pay_run: PayRun) -> bool:
    """
    Detect standalone vacation pay run.
    """

    stubs = list(pay_run.pay_stubs.all())

    if not stubs:
        return False

    return all(is_vacation_pay_stub(pay_stub=stub) for stub in stubs)
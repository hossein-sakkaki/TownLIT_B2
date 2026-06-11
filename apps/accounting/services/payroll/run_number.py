# apps/accounting/services/payroll/run_number.py

from django.utils import timezone


def generate_pay_run_number() -> str:
    """
    Generate a unique pay run number.
    """

    now = timezone.now()
    return now.strftime("PR-%Y%m%d-%H%M%S-%f")
# apps/accounting/services/payroll/remittance_due_date.py

from datetime import date


class PayrollRemitterType:
    """
    Supported CRA remitter types.
    """

    REGULAR_MONTHLY = "regular_monthly"
    QUARTERLY = "quarterly"
    ACCELERATED_THRESHOLD_1 = "accelerated_threshold_1"
    ACCELERATED_THRESHOLD_2 = "accelerated_threshold_2"


def calculate_regular_monthly_due_date(*, pay_date: date) -> date:
    """
    Regular remitter due date: 15th day of the month after payment month.
    """

    year = pay_date.year
    month = pay_date.month + 1

    if month == 13:
        year += 1
        month = 1

    return date(year, month, 15)


def calculate_quarterly_due_date(*, pay_date: date) -> date:
    """
    Quarterly remitter due date: 15th day after quarter end.
    """

    month = pay_date.month

    if month in {1, 2, 3}:
        return date(pay_date.year, 4, 15)

    if month in {4, 5, 6}:
        return date(pay_date.year, 7, 15)

    if month in {7, 8, 9}:
        return date(pay_date.year, 10, 15)

    return date(pay_date.year + 1, 1, 15)


def calculate_accelerated_threshold_1_due_date(*, pay_date: date) -> date:
    """
    Threshold 1:
    - Paid 1st to 15th: due 25th of same month.
    - Paid 16th to month end: due 10th of next month.
    """

    if pay_date.day <= 15:
        return date(pay_date.year, pay_date.month, 25)

    year = pay_date.year
    month = pay_date.month + 1

    if month == 13:
        year += 1
        month = 1

    return date(year, month, 10)


def calculate_remittance_due_date(
    *,
    pay_date: date,
    remitter_type: str = PayrollRemitterType.REGULAR_MONTHLY,
) -> date:
    """
    Calculate CRA payroll remittance due date.
    """

    if remitter_type == PayrollRemitterType.REGULAR_MONTHLY:
        return calculate_regular_monthly_due_date(pay_date=pay_date)

    if remitter_type == PayrollRemitterType.QUARTERLY:
        return calculate_quarterly_due_date(pay_date=pay_date)

    if remitter_type == PayrollRemitterType.ACCELERATED_THRESHOLD_1:
        return calculate_accelerated_threshold_1_due_date(pay_date=pay_date)

    # Threshold 2 needs working-day logic. Keep it explicit for future.
    raise ValueError(f"Unsupported remitter type: {remitter_type}")
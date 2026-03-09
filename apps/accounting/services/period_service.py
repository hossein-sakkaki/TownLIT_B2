# apps/accounting/services/period_service.py

from datetime import date

from apps.accounting.models import AccountingPeriod


class AccountingPeriodError(Exception):
    """Raised when a journal entry date is not allowed."""
    pass


def get_period_for_date(entry_date: date):
    """
    Return the accounting period covering the given date.
    If no periods exist yet, return None to allow migration-friendly rollout.
    """

    if not AccountingPeriod.objects.exists():
        return None

    return AccountingPeriod.objects.filter(
        start_date__lte=entry_date,
        end_date__gte=entry_date,
    ).order_by("start_date").first()


def assert_can_post_to_date(entry_date: date):
    """
    Ensure posting is allowed for the given date.
    Migration-friendly behavior:
    - If no periods exist yet, allow posting.
    - If periods exist, entry date must fall in an OPEN period.
    """

    period = get_period_for_date(entry_date)

    if period is None:
        if AccountingPeriod.objects.exists():
            raise AccountingPeriodError(
                f"No accounting period is configured for date {entry_date}."
            )
        return

    if period.status == AccountingPeriod.STATUS_OPEN:
        return

    if period.status == AccountingPeriod.STATUS_CLOSED:
        raise AccountingPeriodError(
            f"Posting is not allowed because period '{period.code}' is CLOSED."
        )

    if period.status == AccountingPeriod.STATUS_LOCKED:
        raise AccountingPeriodError(
            f"Posting is not allowed because period '{period.code}' is LOCKED."
        )

    raise AccountingPeriodError(
        f"Posting is not allowed for date {entry_date}."
    )
# apps/accounting/services/period_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from datetime import date

from apps.accounting.models import AccountingPeriod


class AccountingPeriodError(Exception):
    """Raised when a posting date is not allowed."""

    pass


def get_period_for_date(
    entry_date: date,
) -> AccountingPeriod | None:
    """Return the monthly control period for a date."""

    monthly_periods = AccountingPeriod.objects.filter(
        period_type=AccountingPeriod.PERIOD_TYPE_MONTH
    )

    if not monthly_periods.exists():
        return None

    matches = list(
        monthly_periods
        .filter(
            start_date__lte=entry_date,
            end_date__gte=entry_date,
        )
        .order_by("start_date", "id")[:2]
    )

    if len(matches) > 1:
        raise AccountingPeriodError(
            f"Multiple monthly accounting periods cover "
            f"{entry_date}. Fix the accounting period configuration."
        )

    return matches[0] if matches else None


def assert_can_post_to_date(
    entry_date: date,
) -> AccountingPeriod | None:
    """Ensure the posting date belongs to an open month."""

    period = get_period_for_date(entry_date)

    monthly_periods_exist = AccountingPeriod.objects.filter(
        period_type=AccountingPeriod.PERIOD_TYPE_MONTH
    ).exists()

    if period is None:
        if monthly_periods_exist:
            raise AccountingPeriodError(
                f"No monthly accounting period is configured "
                f"for date {entry_date}."
            )

        # Migration-friendly rollout.
        return None

    if period.status == AccountingPeriod.STATUS_OPEN:
        return period

    if period.status == AccountingPeriod.STATUS_CLOSED:
        raise AccountingPeriodError(
            f"Posting is not allowed because period "
            f"'{period.code}' is CLOSED."
        )

    if period.status == AccountingPeriod.STATUS_LOCKED:
        raise AccountingPeriodError(
            f"Posting is not allowed because period "
            f"'{period.code}' is LOCKED."
        )

    raise AccountingPeriodError(
        f"Posting is not allowed for date {entry_date}."
    )
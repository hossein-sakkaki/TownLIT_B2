# apps/accounting/services/fund_monitoring_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from decimal import Decimal

from django.db.models import Sum

from apps.accounting.models import Account, JournalEntry, Transaction


ZERO = Decimal("0.00")
EQUIPMENT_PARENT_CODE = "1500"


def _empty_metrics() -> dict:
    return {
        "revenue": ZERO,
        "operating_expense": ZERO,
        "capital_deployed": ZERO,
        "operating_result": ZERO,
        "available_funding": ZERO,
    }


def build_fund_metrics(funds) -> dict[int, dict]:
    """
    Build posted fund activity metrics in one grouped query.
    """

    fund_ids = [item.id for item in funds]
    metrics = {fund_id: _empty_metrics() for fund_id in fund_ids}

    if not fund_ids:
        return metrics

    rows = (
        Transaction.objects.filter(
            fund_id__in=fund_ids,
            journal_entry__status=JournalEntry.STATUS_POSTED,
        )
        .values(
            "fund_id",
            "account__account_type",
            "account__parent__code",
        )
        .annotate(
            debit_total=Sum("debit"),
            credit_total=Sum("credit"),
        )
    )

    for row in rows:
        item = metrics[row["fund_id"]]
        debit = row["debit_total"] or ZERO
        credit = row["credit_total"] or ZERO
        account_type = row["account__account_type"]
        parent_code = row["account__parent__code"]

        if account_type == Account.TYPE_REVENUE:
            item["revenue"] += credit - debit
        elif account_type == Account.TYPE_EXPENSE:
            item["operating_expense"] += debit - credit
        elif account_type == Account.TYPE_ASSET and parent_code == EQUIPMENT_PARENT_CODE:
            item["capital_deployed"] += debit - credit

    for item in metrics.values():
        item["operating_result"] = item["revenue"] - item["operating_expense"]
        item["available_funding"] = (
            item["revenue"]
            - item["operating_expense"]
            - item["capital_deployed"]
        )

    return metrics


def build_budget_line_metrics(lines) -> dict[int, dict]:
    """
    Build actual budget usage including operating and capital deployment.
    """

    line_ids = [item.id for item in lines]
    metrics = {
        line_id: {
            "operating_spend": ZERO,
            "capital_spend": ZERO,
            "actual": ZERO,
        }
        for line_id in line_ids
    }

    if not line_ids:
        return metrics

    rows = (
        Transaction.objects.filter(
            budget_line_id__in=line_ids,
            journal_entry__status=JournalEntry.STATUS_POSTED,
        )
        .values(
            "budget_line_id",
            "account__account_type",
            "account__parent__code",
        )
        .annotate(
            debit_total=Sum("debit"),
            credit_total=Sum("credit"),
        )
    )

    for row in rows:
        item = metrics[row["budget_line_id"]]
        debit = row["debit_total"] or ZERO
        credit = row["credit_total"] or ZERO
        account_type = row["account__account_type"]
        parent_code = row["account__parent__code"]

        if account_type == Account.TYPE_EXPENSE:
            item["operating_spend"] += debit - credit
        elif account_type == Account.TYPE_ASSET and parent_code == EQUIPMENT_PARENT_CODE:
            item["capital_spend"] += debit - credit

    for item in metrics.values():
        item["actual"] = item["operating_spend"] + item["capital_spend"]

    return metrics

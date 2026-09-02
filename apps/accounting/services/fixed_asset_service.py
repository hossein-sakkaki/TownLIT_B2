# apps/accounting/services/fixed_asset_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from decimal import Decimal
from uuid import uuid4

from django.db import transaction

from apps.accounting.models.accounting_period import AccountingPeriod
from apps.accounting.models.budget import BudgetLine
from apps.accounting.models.fixed_asset import FixedAsset, FixedAssetDepreciation
from apps.accounting.services.fund_monitoring_service import build_budget_line_metrics
from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import JournalEntryInput, JournalLineInput


ZERO = Decimal("0.00")


class FixedAssetError(Exception):
    pass


def _assert_capital_budget_capacity(*, fund=None, budget_line=None, amount=ZERO) -> None:
    if not fund or not budget_line:
        return

    policy = getattr(fund, "policy", None)
    if not policy or not policy.prevent_budget_overrun:
        return

    locked_line = (
        BudgetLine.objects.select_for_update()
        .select_related("budget", "budget__fund")
        .get(pk=budget_line.pk)
    )

    if locked_line.budget.fund_id != fund.id:
        raise FixedAssetError("The selected budget line belongs to a different fund.")

    current = build_budget_line_metrics([locked_line])[locked_line.id]["actual"]
    approved = locked_line.approved_amount or ZERO
    projected = current + Decimal(amount).quantize(Decimal("0.01"))

    if projected > approved:
        raise FixedAssetError(
            f"Capital purchase would exceed budget line '{locked_line.code}'. "
            f"Approved={approved}, Current={current}, New={amount}, Projected={projected}."
        )


def _tracking_kwargs(*, fund=None, budget_line=None) -> dict:
    payload = {}
    if fund:
        payload["fund_code"] = fund.code
    if budget_line:
        payload["budget_line_id"] = budget_line.id
        payload["budget_line_code"] = budget_line.code
        payload["budget_plan_code"] = budget_line.budget.code
    return payload


@transaction.atomic
def purchase_fixed_asset(
    *,
    name,
    purchase_date,
    placed_in_service_date,
    cost,
    salvage_value,
    useful_life_months,
    bank_account,
    asset_account,
    accumulated_depreciation_account,
    depreciation_expense_account,
    description="",
    vendor_name="",
    reference="",
    serial_number="",
    fund=None,
    budget_line=None,
    created_by=None,
):
    cost = Decimal(cost).quantize(Decimal("0.01"))
    salvage_value = Decimal(salvage_value or ZERO).quantize(Decimal("0.01"))

    _assert_capital_budget_capacity(fund=fund, budget_line=budget_line, amount=cost)

    asset = FixedAsset(
        name=name.strip(),
        description=(description or "").strip(),
        asset_account=asset_account,
        accumulated_depreciation_account=accumulated_depreciation_account,
        depreciation_expense_account=depreciation_expense_account,
        acquisition_bank_account=bank_account,
        purchase_date=purchase_date,
        placed_in_service_date=placed_in_service_date,
        cost=cost,
        salvage_value=salvage_value,
        useful_life_months=useful_life_months,
        vendor_name=(vendor_name or "").strip(),
        reference=(reference or "").strip(),
        serial_number=(serial_number or "").strip(),
        fund=fund,
        budget_line=budget_line,
        created_by=created_by,
    )
    asset.full_clean()

    tracking = _tracking_kwargs(fund=fund, budget_line=budget_line)
    source_ref = uuid4().hex

    journal_entry = post_journal_entry(
        JournalEntryInput(
            entry_date=purchase_date,
            description=f"Capital asset purchase - {asset.name}",
            reference=(reference or "").strip(),
            source_app="accounting",
            source_model="fixed_asset_acquisition",
            source_ref=source_ref,
            created_by=created_by,
            approved_by=created_by,
            lines=[
                JournalLineInput(
                    line_number=1,
                    account_code=asset_account.code,
                    debit=cost,
                    memo=asset.name,
                    **tracking,
                ),
                JournalLineInput(
                    line_number=2,
                    account_code=bank_account.ledger_account.code,
                    credit=cost,
                    memo=(reference or asset.name).strip(),
                ),
            ],
        )
    )

    asset.acquisition_journal_entry = journal_entry
    asset.save()
    return asset


def _depreciation_amount_for_period(asset: FixedAsset) -> Decimal:
    remaining = asset.depreciable_amount - asset.accumulated_depreciation
    remaining = max(remaining, ZERO)

    if remaining <= ZERO:
        return ZERO

    monthly = asset.monthly_depreciation_amount
    if monthly <= ZERO:
        return ZERO

    return min(monthly, remaining).quantize(Decimal("0.01"))


@transaction.atomic
def post_asset_depreciation_for_period(*, asset, period, user=None):
    asset = FixedAsset.objects.select_for_update().get(pk=asset.pk)

    if asset.status == FixedAsset.STATUS_DISPOSED:
        raise FixedAssetError("Disposed assets cannot receive depreciation.")

    if asset.placed_in_service_date > period.end_date:
        return None

    if period.period_type != AccountingPeriod.PERIOD_TYPE_MONTH:
        raise FixedAssetError("Depreciation must be posted to a monthly accounting period.")

    if period.status != AccountingPeriod.STATUS_OPEN:
        raise FixedAssetError("Depreciation can only be posted to an OPEN accounting period.")

    existing = FixedAssetDepreciation.objects.filter(
        asset=asset,
        period_start=period.start_date,
        period_end=period.end_date,
    ).first()
    if existing:
        return existing

    amount = _depreciation_amount_for_period(asset)
    if amount <= ZERO:
        if asset.status != FixedAsset.STATUS_FULLY_DEPRECIATED:
            asset.status = FixedAsset.STATUS_FULLY_DEPRECIATED
            asset.save(update_fields=["status", "updated_at"])
        return None

    source_ref = f"{asset.public_id}:{period.code}"
    journal_entry = post_journal_entry(
        JournalEntryInput(
            entry_date=period.end_date,
            description=f"Depreciation - {asset.asset_number} - {asset.name}",
            reference=asset.asset_number,
            source_app="accounting",
            source_model="fixed_asset_depreciation",
            source_ref=source_ref,
            created_by=user,
            approved_by=user,
            lines=[
                JournalLineInput(
                    line_number=1,
                    account_code=asset.depreciation_expense_account.code,
                    debit=amount,
                    memo=f"Depreciation expense - {asset.name}",
                ),
                JournalLineInput(
                    line_number=2,
                    account_code=asset.accumulated_depreciation_account.code,
                    credit=amount,
                    memo=f"Accumulated depreciation - {asset.name}",
                ),
            ],
        )
    )

    item = FixedAssetDepreciation.objects.create(
        asset=asset,
        period_start=period.start_date,
        period_end=period.end_date,
        amount=amount,
        journal_entry=journal_entry,
        posted_by=user,
    )

    if asset.accumulated_depreciation >= asset.depreciable_amount:
        asset.status = FixedAsset.STATUS_FULLY_DEPRECIATED
        asset.save(update_fields=["status", "updated_at"])

    return item


@transaction.atomic
def post_depreciation_for_open_period(*, period, user=None) -> dict:
    if period.period_type != AccountingPeriod.PERIOD_TYPE_MONTH:
        raise FixedAssetError("Select a monthly accounting period.")
    if period.status != AccountingPeriod.STATUS_OPEN:
        raise FixedAssetError("Selected accounting period must be OPEN.")

    assets = list(
        FixedAsset.objects.select_for_update()
        .filter(
            status__in=(
                FixedAsset.STATUS_ACTIVE,
                FixedAsset.STATUS_FULLY_DEPRECIATED,
            ),
            placed_in_service_date__lte=period.end_date,
        )
        .select_related(
            "asset_account",
            "accumulated_depreciation_account",
            "depreciation_expense_account",
        )
        .order_by("asset_number")
    )

    posted = 0
    skipped = 0

    for asset in assets:
        before = FixedAssetDepreciation.objects.filter(
            asset=asset,
            period_start=period.start_date,
            period_end=period.end_date,
        ).exists()

        item = post_asset_depreciation_for_period(asset=asset, period=period, user=user)
        if item is not None and not before:
            posted += 1
        else:
            skipped += 1

    return {
        "posted": posted,
        "skipped": skipped,
        "asset_count": len(assets),
    }

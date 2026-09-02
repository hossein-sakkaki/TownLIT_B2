# apps/accounting/services/vendor_ap_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from collections import defaultdict
from decimal import Decimal
import uuid

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import (
    Account,
    BudgetLine,
    FixedAsset,
    FundPolicy,
    Vendor,
    VendorAPAttachment,
    VendorBill,
    VendorBillLine,
    VendorPayment,
    VendorPaymentAllocation,
)
from apps.accounting.services.account_lookup import AccountCodes
from apps.accounting.services.fund_monitoring_service import build_budget_line_metrics
from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import JournalEntryInput, JournalLineInput


ZERO = Decimal("0.00")
ACCUMULATED_DEPRECIATION_CODE = "1590"
DEPRECIATION_EXPENSE_CODE = "5390"


class VendorAPError(Exception):
    pass


def _money(value) -> Decimal:
    return Decimal(str(value or ZERO)).quantize(Decimal("0.01"))


def _tracking_kwargs(line: VendorBillLine) -> dict:
    payload = {}
    if line.fund_id:
        payload["fund_code"] = line.fund.code
    if line.budget_line_id:
        payload["budget_code"] = line.budget_line.code
    return payload


def refresh_bill_totals(*, bill: VendorBill) -> VendorBill:
    """Refresh draft totals from line data."""

    totals = bill.lines.aggregate(
        subtotal=Sum("amount"),
        tax_total=Sum("tax_amount"),
    )
    subtotal = _money(totals["subtotal"])
    tax_total = _money(totals["tax_total"])
    total = subtotal + tax_total

    VendorBill.objects.filter(pk=bill.pk).update(
        subtotal=subtotal,
        tax_total=tax_total,
        total_amount=total,
        updated_at=timezone.now(),
    )
    bill.subtotal = subtotal
    bill.tax_total = tax_total
    bill.total_amount = total
    return bill


def _validate_budget_capacity(*, lines: list[VendorBillLine]) -> None:
    """Preflight combined operating/capital budget impact for this bill."""

    proposed = defaultdict(lambda: ZERO)
    line_map = {}

    for line in lines:
        if not line.budget_line_id or not line.fund_id:
            continue
        policy = getattr(line.fund, "policy", None)
        if not policy or not policy.prevent_budget_overrun:
            continue
        proposed[line.budget_line_id] += _money(line.primary_posting_amount)
        line_map[line.budget_line_id] = line

    if not proposed:
        return

    locked = list(
        BudgetLine.objects.select_for_update()
        .select_related("budget", "budget__fund")
        .filter(pk__in=proposed.keys())
    )
    metrics = build_budget_line_metrics(locked)

    for budget_line in locked:
        source_line = line_map[budget_line.id]
        if budget_line.budget.fund_id != source_line.fund_id:
            raise VendorAPError("Budget line belongs to a different fund.")
        current = _money(metrics[budget_line.id]["actual"])
        approved = _money(budget_line.approved_amount)
        projected = current + _money(proposed[budget_line.id])
        if projected > approved:
            raise VendorAPError(
                f"Budget overrun for '{budget_line.code}'. "
                f"Approved={approved}, Current={current}, Bill={proposed[budget_line.id]}, Projected={projected}."
            )


def _fixed_asset_accounts():
    accumulated = Account.objects.filter(
        code=ACCUMULATED_DEPRECIATION_CODE,
        account_type=Account.TYPE_ASSET,
        is_active=True,
        allows_posting=True,
    ).first()
    depreciation_expense = Account.objects.filter(
        code=DEPRECIATION_EXPENSE_CODE,
        account_type=Account.TYPE_EXPENSE,
        is_active=True,
        allows_posting=True,
    ).first()
    if not accumulated or not depreciation_expense:
        raise VendorAPError("Fixed-asset accounts 1590 and 5390 must be configured before posting capital bill lines.")
    return accumulated, depreciation_expense


@transaction.atomic
def post_vendor_bill(*, bill: VendorBill, user=None) -> VendorBill:
    """Recognize a draft vendor bill into expense/asset and Vendor Payable."""

    locked = (
        VendorBill.objects.select_for_update()
        .select_related("vendor")
        .get(pk=bill.pk)
    )
    if locked.status != VendorBill.STATUS_DRAFT or locked.posting_journal_entry_id:
        raise VendorAPError("Only an unposted draft bill can be posted.")

    lines = list(
        locked.lines.select_related(
            "account",
            "tax_account",
            "fund",
            "fund__policy",
            "budget_line",
            "budget_line__budget",
        ).order_by("line_number", "id")
    )
    if not lines:
        raise VendorAPError("Add at least one bill line before posting.")

    for line in lines:
        line.full_clean()

    refresh_bill_totals(bill=locked)
    if locked.total_amount <= ZERO:
        raise VendorAPError("Bill total must be greater than zero.")

    _validate_budget_capacity(lines=lines)

    posting_lines = []
    line_number = 1
    has_capital = any(line.capitalize_as_fixed_asset for line in lines)
    accumulated = depreciation_expense = None
    if has_capital:
        accumulated, depreciation_expense = _fixed_asset_accounts()

    for line in lines:
        tracking = _tracking_kwargs(line)
        primary_amount = _money(line.primary_posting_amount)
        posting_lines.append(
            JournalLineInput(
                line_number=line_number,
                account_code=line.account.code,
                debit=primary_amount,
                memo=line.description,
                **tracking,
            )
        )
        line_number += 1

        if line.tax_account_id and line.tax_amount > ZERO:
            posting_lines.append(
                JournalLineInput(
                    line_number=line_number,
                    account_code=line.tax_account.code,
                    debit=_money(line.tax_amount),
                    memo=f"Recoverable tax - {line.description}",
                )
            )
            line_number += 1

    posting_lines.append(
        JournalLineInput(
            line_number=line_number,
            account_code=AccountCodes.VENDOR_PAYABLE,
            credit=_money(locked.total_amount),
            memo=f"Vendor payable - {locked.vendor}",
        )
    )

    journal_entry = post_journal_entry(
        JournalEntryInput(
            entry_date=locked.bill_date,
            description=locked.description or f"Vendor bill - {locked.vendor} - {locked.bill_number}",
            reference=locked.bill_number,
            source_app="accounting",
            source_model="vendor_bill",
            source_ref=str(locked.id),
            currency=locked.currency,
            created_by=user,
            approved_by=user,
            lines=posting_lines,
        )
    )

    now = timezone.now()
    VendorBill.objects.filter(pk=locked.pk).update(
        posting_journal_entry=journal_entry,
        posted_at=now,
        posted_by=user,
        status=VendorBill.STATUS_OPEN,
        updated_at=now,
    )

    if has_capital:
        for line in lines:
            if not line.capitalize_as_fixed_asset:
                continue
            asset = FixedAsset.objects.create(
                name=line.asset_name.strip(),
                description=line.description,
                asset_account=line.account,
                accumulated_depreciation_account=accumulated,
                depreciation_expense_account=depreciation_expense,
                acquisition_bank_account=None,
                purchase_date=locked.bill_date,
                placed_in_service_date=line.placed_in_service_date,
                cost=_money(line.primary_posting_amount),
                salvage_value=_money(line.salvage_value),
                useful_life_months=line.useful_life_months,
                vendor_name=str(locked.vendor),
                reference=locked.bill_number,
                serial_number=line.serial_number,
                fund=line.fund,
                budget_line=line.budget_line,
                acquisition_journal_entry=journal_entry,
                created_by=user,
            )
            VendorBillLine.objects.filter(pk=line.pk).update(fixed_asset=asset)

    return VendorBill.objects.select_related("vendor", "posting_journal_entry").get(pk=locked.pk)


@transaction.atomic
def record_vendor_payment(
    *,
    vendor: Vendor,
    allocations: list[tuple[VendorBill, Decimal]],
    payment_date,
    bank_account,
    payment_method: str,
    reference: str,
    note: str = "",
    user=None,
) -> VendorPayment:
    """Pay one or more posted bills for the same vendor in one bank payment."""

    if not reference or not reference.strip():
        raise VendorAPError("Payment reference is required.")
    if not vendor.is_active:
        raise VendorAPError("Vendor is inactive.")
    if VendorPayment.objects.filter(vendor=vendor, reference=reference.strip()).exists():
        raise VendorAPError("This payment reference has already been used for this vendor.")
    if not allocations:
        raise VendorAPError("Select at least one bill to pay.")
    if not bank_account.is_active or bank_account.status != bank_account.STATUS_ACTIVE:
        raise VendorAPError("Select an active bank account.")
    if not bank_account.ledger_account.is_active or not bank_account.ledger_account.allows_posting:
        raise VendorAPError("Bank ledger account is not active/postable.")

    normalized = []
    seen = set()
    for bill, raw_amount in allocations:
        if bill.pk in seen:
            raise VendorAPError("A bill cannot be allocated twice in one payment.")
        seen.add(bill.pk)
        amount = _money(raw_amount)
        if amount <= ZERO:
            continue
        normalized.append((bill.pk, amount))
    if not normalized:
        raise VendorAPError("Payment amount must be greater than zero.")

    locked_bills = {
        item.pk: item
        for item in VendorBill.objects.select_for_update()
        .select_related("vendor")
        .filter(pk__in=[pk for pk, _ in normalized])
    }
    if len(locked_bills) != len(normalized):
        raise VendorAPError("One or more selected bills no longer exist.")

    bill_currencies = {locked_bills[bill_id].currency for bill_id, _ in normalized}
    if len(bill_currencies) != 1:
        raise VendorAPError("One payment cannot mix bills with different currencies.")
    payment_currency = next(iter(bill_currencies))
    if payment_currency != bank_account.currency:
        raise VendorAPError(
            f"Bill currency {payment_currency} does not match bank account currency {bank_account.currency}. "
            "Foreign-currency payments require an FX workflow."
        )

    final_allocations = []
    total = ZERO
    for bill_id, amount in normalized:
        bill = locked_bills[bill_id]
        if bill.vendor_id != vendor.id:
            raise VendorAPError("All bills in one payment must belong to the same vendor.")
        if bill.status not in {VendorBill.STATUS_OPEN, VendorBill.STATUS_PARTIAL}:
            raise VendorAPError(f"Bill {bill.bill_number} is not open for payment.")
        outstanding = _money(bill.outstanding_amount)
        if amount > outstanding:
            raise VendorAPError(
                f"Payment for bill {bill.bill_number} cannot exceed outstanding amount {outstanding}."
            )
        final_allocations.append((bill, amount))
        total += amount

    public_id = uuid.uuid4()
    source_ref = str(public_id)
    journal_entry = post_journal_entry(
        JournalEntryInput(
            entry_date=payment_date,
            description=f"Vendor payment - {vendor}",
            reference=reference.strip(),
            source_app="accounting",
            source_model="vendor_payment",
            source_ref=source_ref,
            created_by=user,
            approved_by=user,
            lines=[
                JournalLineInput(
                    line_number=1,
                    account_code=AccountCodes.VENDOR_PAYABLE,
                    debit=total,
                    memo=f"Reduce vendor payable - {vendor}",
                ),
                JournalLineInput(
                    line_number=2,
                    account_code=bank_account.ledger_account.code,
                    credit=total,
                    memo=reference.strip(),
                ),
            ],
        )
    )

    payment = VendorPayment.objects.create(
        public_id=public_id,
        vendor=vendor,
        payment_date=payment_date,
        bank_account=bank_account,
        amount=total,
        currency=payment_currency,
        payment_method=payment_method,
        reference=reference.strip(),
        note=note,
        journal_entry=journal_entry,
        created_by=user,
    )

    for bill, amount in final_allocations:
        VendorPaymentAllocation.objects.create(
            payment=payment,
            bill=bill,
            amount=amount,
        )
        new_paid = _money(bill.amount_paid) + amount
        new_status = (
            VendorBill.STATUS_PAID
            if new_paid >= _money(bill.total_amount)
            else VendorBill.STATUS_PARTIAL
        )
        VendorBill.objects.filter(pk=bill.pk).update(
            amount_paid=new_paid,
            status=new_status,
            updated_at=timezone.now(),
        )

    return payment

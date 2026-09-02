# apps/accounting/services/customer_ar_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from decimal import Decimal
import uuid

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import (
    Customer,
    CustomerInvoice,
    CustomerInvoiceLine,
    CustomerReceipt,
    CustomerReceiptAllocation,
)
from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import JournalEntryInput, JournalLineInput


ZERO = Decimal("0.00")


class CustomerARError(Exception):
    pass


def _money(value) -> Decimal:
    return Decimal(str(value or ZERO)).quantize(Decimal("0.01"))


def _tracking_kwargs(line: CustomerInvoiceLine) -> dict:
    payload = {}
    if line.fund_id:
        payload["fund_code"] = line.fund.code
    return payload


def refresh_invoice_totals(*, invoice: CustomerInvoice) -> CustomerInvoice:
    """Refresh draft totals from invoice lines."""

    totals = invoice.lines.aggregate(
        subtotal=Sum("amount"),
        tax_total=Sum("tax_amount"),
    )
    subtotal = _money(totals["subtotal"])
    tax_total = _money(totals["tax_total"])
    total = subtotal + tax_total

    CustomerInvoice.objects.filter(pk=invoice.pk).update(
        subtotal=subtotal,
        tax_total=tax_total,
        total_amount=total,
        updated_at=timezone.now(),
    )
    invoice.subtotal = subtotal
    invoice.tax_total = tax_total
    invoice.total_amount = total
    return invoice


@transaction.atomic
def post_customer_invoice(*, invoice: CustomerInvoice, user=None) -> CustomerInvoice:
    """Recognize a draft customer invoice into revenue and Accounts Receivable."""

    locked = (
        CustomerInvoice.objects.select_for_update()
        .select_related("customer", "receivable_account")
        .get(pk=invoice.pk)
    )
    if locked.status != CustomerInvoice.STATUS_DRAFT or locked.posting_journal_entry_id:
        raise CustomerARError("Only an unposted draft invoice can be posted.")
    if not locked.customer.is_active:
        raise CustomerARError("Customer is inactive.")

    lines = list(
        locked.lines.select_related(
            "revenue_account",
            "tax_account",
            "fund",
        ).order_by("line_number", "id")
    )
    if not lines:
        raise CustomerARError("Add at least one invoice line before posting.")

    for line in lines:
        line.full_clean()

    refresh_invoice_totals(invoice=locked)
    if locked.total_amount <= ZERO:
        raise CustomerARError("Invoice total must be greater than zero.")

    posting_lines = [
        JournalLineInput(
            line_number=1,
            account_code=locked.receivable_account.code,
            debit=_money(locked.total_amount),
            memo=f"Accounts receivable - {locked.customer} - {locked.invoice_number}",
        )
    ]
    line_number = 2

    for line in lines:
        posting_lines.append(
            JournalLineInput(
                line_number=line_number,
                account_code=line.revenue_account.code,
                credit=_money(line.amount),
                memo=line.description,
                **_tracking_kwargs(line),
            )
        )
        line_number += 1

        if line.tax_amount > ZERO:
            if not line.tax_account_id:
                raise CustomerARError(
                    f"Invoice line {line.line_number} has tax but no Sales Tax Payable account."
                )
            posting_lines.append(
                JournalLineInput(
                    line_number=line_number,
                    account_code=line.tax_account.code,
                    credit=_money(line.tax_amount),
                    memo=f"Sales tax - {line.description}",
                )
            )
            line_number += 1

    journal_entry = post_journal_entry(
        JournalEntryInput(
            entry_date=locked.invoice_date,
            description=locked.description or f"Customer invoice - {locked.customer} - {locked.invoice_number}",
            reference=locked.invoice_number,
            source_app="accounting",
            source_model="customer_invoice",
            source_ref=str(locked.id),
            currency=locked.currency,
            created_by=user,
            approved_by=user,
            lines=posting_lines,
        )
    )

    now = timezone.now()
    CustomerInvoice.objects.filter(pk=locked.pk).update(
        posting_journal_entry=journal_entry,
        posted_at=now,
        posted_by=user,
        status=CustomerInvoice.STATUS_OPEN,
        updated_at=now,
    )

    return CustomerInvoice.objects.select_related(
        "customer",
        "receivable_account",
        "posting_journal_entry",
    ).get(pk=locked.pk)


@transaction.atomic
def record_customer_receipt(
    *,
    customer: Customer,
    allocations: list[tuple[CustomerInvoice, Decimal]],
    receipt_date,
    bank_account,
    payment_method: str,
    reference: str,
    note: str = "",
    user=None,
) -> CustomerReceipt:
    """Receive one bank payment and allocate it across customer invoices."""

    clean_reference = (reference or "").strip()
    if not clean_reference:
        raise CustomerARError("Receipt reference is required.")
    if not customer.is_active:
        raise CustomerARError("Customer is inactive.")
    if CustomerReceipt.objects.filter(customer=customer, reference=clean_reference).exists():
        raise CustomerARError("This receipt reference has already been used for this customer.")
    if not allocations:
        raise CustomerARError("Select at least one invoice to receive.")
    if not bank_account.is_active or bank_account.status != bank_account.STATUS_ACTIVE:
        raise CustomerARError("Select an active bank account.")
    if not bank_account.ledger_account.is_active or not bank_account.ledger_account.allows_posting:
        raise CustomerARError("Bank ledger account is not active/postable.")

    normalized = []
    seen = set()
    for invoice, raw_amount in allocations:
        if invoice.pk in seen:
            raise CustomerARError("An invoice cannot be allocated twice in one receipt.")
        seen.add(invoice.pk)
        amount = _money(raw_amount)
        if amount <= ZERO:
            continue
        normalized.append((invoice.pk, amount))

    if not normalized:
        raise CustomerARError("Receipt amount must be greater than zero.")

    locked_invoices = {
        item.pk: item
        for item in CustomerInvoice.objects.select_for_update()
        .select_related("customer", "receivable_account")
        .filter(pk__in=[pk for pk, _ in normalized])
    }
    if len(locked_invoices) != len(normalized):
        raise CustomerARError("One or more selected invoices no longer exist.")

    invoice_currencies = {locked_invoices[invoice_id].currency for invoice_id, _ in normalized}
    if len(invoice_currencies) != 1:
        raise CustomerARError("One receipt cannot mix invoices with different currencies.")
    receipt_currency = next(iter(invoice_currencies))
    if receipt_currency != bank_account.currency:
        raise CustomerARError(
            f"Invoice currency {receipt_currency} does not match bank account currency {bank_account.currency}. "
            "Foreign-currency receipts require an FX workflow."
        )

    final_allocations = []
    total = ZERO
    for invoice_id, amount in normalized:
        invoice = locked_invoices[invoice_id]
        if invoice.customer_id != customer.id:
            raise CustomerARError("All invoices in one receipt must belong to the same customer.")
        if invoice.status not in {CustomerInvoice.STATUS_OPEN, CustomerInvoice.STATUS_PARTIAL}:
            raise CustomerARError(f"Invoice {invoice.invoice_number} is not open for receipt.")
        if not invoice.posting_journal_entry_id:
            raise CustomerARError(f"Invoice {invoice.invoice_number} has not been posted to Accounts Receivable.")

        outstanding = _money(invoice.outstanding_amount)
        if amount > outstanding:
            raise CustomerARError(
                f"Receipt for invoice {invoice.invoice_number} cannot exceed outstanding amount {outstanding}."
            )

        final_allocations.append((invoice, amount))
        total += amount

    public_id = uuid.uuid4()
    posting_lines = [
        JournalLineInput(
            line_number=1,
            account_code=bank_account.ledger_account.code,
            debit=total,
            memo=clean_reference,
        )
    ]

    line_number = 2
    for invoice, amount in final_allocations:
        posting_lines.append(
            JournalLineInput(
                line_number=line_number,
                account_code=invoice.receivable_account.code,
                credit=amount,
                memo=f"Apply receipt to {invoice.invoice_number}",
            )
        )
        line_number += 1

    journal_entry = post_journal_entry(
        JournalEntryInput(
            entry_date=receipt_date,
            description=f"Customer receipt - {customer}",
            reference=clean_reference,
            source_app="accounting",
            source_model="customer_receipt",
            source_ref=str(public_id),
            currency=receipt_currency,
            created_by=user,
            approved_by=user,
            lines=posting_lines,
        )
    )

    receipt = CustomerReceipt.objects.create(
        public_id=public_id,
        customer=customer,
        receipt_date=receipt_date,
        bank_account=bank_account,
        amount=total,
        currency=receipt_currency,
        payment_method=payment_method,
        reference=clean_reference,
        note=note,
        journal_entry=journal_entry,
        created_by=user,
    )

    for invoice, amount in final_allocations:
        CustomerReceiptAllocation.objects.create(
            receipt=receipt,
            invoice=invoice,
            amount=amount,
        )
        new_received = _money(invoice.amount_received) + amount
        new_status = (
            CustomerInvoice.STATUS_PAID
            if new_received >= _money(invoice.total_amount)
            else CustomerInvoice.STATUS_PARTIAL
        )
        CustomerInvoice.objects.filter(pk=invoice.pk).update(
            amount_received=new_received,
            status=new_status,
            updated_at=timezone.now(),
        )

    return receipt

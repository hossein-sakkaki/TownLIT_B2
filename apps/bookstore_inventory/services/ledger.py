# apps/bookstore_inventory/services/ledger.py

from apps.bookstore_inventory.constants import CashEntryDirection, CashEntryType, OrderType
from apps.bookstore_inventory.models import CashLedgerEntry


def sync_inbound_payment_to_ledger(payment):
    # Sync outbound supplier payment to ledger
    shipment = payment.shipment

    return CashLedgerEntry.objects.update_or_create(
        reference_type="inbound_payment",
        reference_id=str(payment.pk),
        defaults={
            "direction": CashEntryDirection.OUT,
            "entry_type": CashEntryType.PURCHASE_PAYMENT,
            "amount": payment.amount,
            "currency": payment.currency,
            "entry_date": payment.paid_at,
            "notes": f"Shipment {shipment.shipment_number} payment",
            "recorded_by": payment.recorded_by,
        },
    )[0]


def delete_inbound_payment_from_ledger(payment):
    # Remove outbound supplier payment from ledger
    CashLedgerEntry.objects.filter(
        reference_type="inbound_payment",
        reference_id=str(payment.pk),
    ).delete()


def sync_order_payment_to_ledger(payment):
    # Sync customer payment to ledger
    order = payment.order
    entry_type = CashEntryType.SALES_INCOME

    if order.order_type == OrderType.DONATION_BASED:
        entry_type = CashEntryType.DONATION_INCOME

    return CashLedgerEntry.objects.update_or_create(
        reference_type="order_payment",
        reference_id=str(payment.pk),
        defaults={
            "direction": CashEntryDirection.IN,
            "entry_type": entry_type,
            "amount": payment.amount,
            "currency": payment.currency,
            "entry_date": payment.received_at,
            "notes": f"Order {order.order_number} payment",
            "recorded_by": payment.received_by,
        },
    )[0]


def delete_order_payment_from_ledger(payment):
    # Remove customer payment from ledger
    CashLedgerEntry.objects.filter(
        reference_type="order_payment",
        reference_id=str(payment.pk),
    ).delete()
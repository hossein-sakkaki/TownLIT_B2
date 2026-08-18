# apps/bookstore_inventory/services/ledger.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from apps.bookstore_inventory.constants import CashEntryDirection, CashEntryType, OrderType
from apps.bookstore_inventory.models import CashLedgerEntry


def sync_inbound_payment_to_ledger(payment):
    shipment = payment.shipment
    return CashLedgerEntry.objects.update_or_create(
        ledger_key=f"inbound_payment:{payment.pk}",
        defaults={
            "reference_type": "inbound_payment",
            "reference_id": str(payment.pk),
            "direction": CashEntryDirection.OUT,
            "entry_type": CashEntryType.PURCHASE_PAYMENT,
            "amount": payment.cash_amount,
            "currency": payment.cash_currency,
            "entry_date": payment.paid_at,
            "notes": (
                f"Shipment {shipment.shipment_number} payment; applied "
                f"{payment.amount} {payment.currency}"
            ),
            "recorded_by": payment.recorded_by,
        },
    )[0]


def delete_inbound_payment_from_ledger(payment):
    CashLedgerEntry.objects.filter(
        ledger_key=f"inbound_payment:{payment.pk}"
    ).delete()


def sync_order_payment_to_ledger(payment):
    entry_type = (
        CashEntryType.DONATION_INCOME
        if payment.order.order_type == OrderType.DONATION_BASED
        else CashEntryType.SALES_INCOME
    )
    return CashLedgerEntry.objects.update_or_create(
        ledger_key=f"order_payment:{payment.pk}",
        defaults={
            "reference_type": "order_payment",
            "reference_id": str(payment.pk),
            "direction": CashEntryDirection.IN,
            "entry_type": entry_type,
            "amount": payment.amount,
            "currency": payment.currency,
            "entry_date": payment.received_at,
            "notes": f"Order {payment.order.order_number} payment",
            "recorded_by": payment.received_by,
        },
    )[0]


def delete_order_payment_from_ledger(payment):
    CashLedgerEntry.objects.filter(
        ledger_key=f"order_payment:{payment.pk}"
    ).delete()

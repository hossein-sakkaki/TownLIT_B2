# apps/bookstore_inventory/signals.py

from decimal import Decimal

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.bookstore_inventory.models import (
    BookOrderItem,
    InboundPayment,
    InboundShipmentItem,
    PaymentRecord,
    StockMovement,
)
from apps.bookstore_inventory.services.balances import rebuild_inventory_balance
from apps.bookstore_inventory.services.ledger import (
    delete_inbound_payment_from_ledger,
    delete_order_payment_from_ledger,
    sync_inbound_payment_to_ledger,
    sync_order_payment_to_ledger,
)
from apps.bookstore_inventory.services.orders import rebuild_order_totals


@receiver(post_save, sender=StockMovement)
def stock_movement_saved(sender, instance, **kwargs):
    # Keep balance updated
    rebuild_inventory_balance(
        warehouse_id=instance.warehouse_id,
        book_edition_id=instance.book_edition_id,
    )


@receiver(post_delete, sender=StockMovement)
def stock_movement_deleted(sender, instance, **kwargs):
    # Rebuild balance after delete
    rebuild_inventory_balance(
        warehouse_id=instance.warehouse_id,
        book_edition_id=instance.book_edition_id,
    )


@receiver(post_save, sender=BookOrderItem)
def order_item_saved(sender, instance, **kwargs):
    # Keep order totals updated
    rebuild_order_totals(order_id=instance.order_id)


@receiver(post_delete, sender=BookOrderItem)
def order_item_deleted(sender, instance, **kwargs):
    # Rebuild order after delete
    rebuild_order_totals(order_id=instance.order_id)


@receiver(post_save, sender=PaymentRecord)
def payment_saved(sender, instance, **kwargs):
    # Keep payment summary and ledger updated
    rebuild_order_totals(order_id=instance.order_id)
    sync_order_payment_to_ledger(instance)


@receiver(post_delete, sender=PaymentRecord)
def payment_deleted(sender, instance, **kwargs):
    # Rebuild payment summary and ledger after delete
    rebuild_order_totals(order_id=instance.order_id)
    delete_order_payment_from_ledger(instance)


@receiver(post_save, sender=InboundShipmentItem)
def inbound_item_saved(sender, instance, **kwargs):
    # Recalculate inbound totals
    instance.shipment.recalculate_totals(save=True)


@receiver(post_delete, sender=InboundShipmentItem)
def inbound_item_deleted(sender, instance, **kwargs):
    # Recalculate inbound totals after delete
    instance.shipment.recalculate_totals(save=True)


@receiver(post_save, sender=InboundPayment)
def inbound_payment_saved(sender, instance, **kwargs):
    # Update paid amount and ledger
    shipment = instance.shipment
    total_paid = sum((payment.amount for payment in shipment.payments.all()), Decimal("0.00"))
    shipment.amount_paid = total_paid
    shipment.recalculate_totals(save=True)
    sync_inbound_payment_to_ledger(instance)


@receiver(post_delete, sender=InboundPayment)
def inbound_payment_deleted(sender, instance, **kwargs):
    # Update paid amount and ledger after delete
    shipment = instance.shipment
    total_paid = sum((payment.amount for payment in shipment.payments.all()), Decimal("0.00"))
    shipment.amount_paid = total_paid
    shipment.recalculate_totals(save=True)
    delete_inbound_payment_from_ledger(instance)
# apps/bookstore_inventory/signals.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.bookstore_inventory.models import (
    BookEdition, BookOrderItem, EditionPrice, InboundPayment,
    InboundPaymentSchedule, InboundShipmentItem, PaymentRecord,
    StockMovement, StockReservation,
)
from apps.bookstore_inventory.services.balances import rebuild_inventory_balance
from apps.bookstore_inventory.services.ledger import (
    delete_inbound_payment_from_ledger, delete_order_payment_from_ledger,
    sync_inbound_payment_to_ledger, sync_order_payment_to_ledger,
)
from apps.bookstore_inventory.services.orders import rebuild_order_totals


PRICE_FIELDS = ("pricing_mode", "fixed_price", "minimum_donation", "currency")


@receiver(pre_save, sender=InboundPayment)
def remember_previous_inbound_schedule(sender, instance, **kwargs):
    if not instance.pk:
        instance._bookstore_previous_schedule_id = None
        return
    instance._bookstore_previous_schedule_id = InboundPayment.objects.filter(
        pk=instance.pk
    ).values_list("schedule_id", flat=True).first()


def _refresh_inbound_schedule(schedule_id):
    if not schedule_id:
        return
    schedule = InboundPaymentSchedule.objects.filter(pk=schedule_id).first()
    if schedule:
        schedule.refresh_status()


@receiver(pre_save, sender=BookEdition)
def remember_edition_price_change(sender, instance, **kwargs):
    if not instance.pk:
        instance._bookstore_price_changed = True
        return
    previous = BookEdition.objects.filter(pk=instance.pk).values(*PRICE_FIELDS).first()
    instance._bookstore_price_changed = bool(
        previous and any(previous[field] != getattr(instance, field) for field in PRICE_FIELDS)
    )


@receiver(post_save, sender=BookEdition)
def record_edition_price_change(sender, instance, **kwargs):
    if not getattr(instance, "_bookstore_price_changed", False):
        return
    now = timezone.now()
    EditionPrice.objects.filter(edition=instance, valid_until__isnull=True).update(
        valid_until=now, updated_at=now,
    )
    EditionPrice.objects.create(
        edition=instance, pricing_mode=instance.pricing_mode,
        fixed_price=instance.fixed_price,
        minimum_donation=instance.minimum_donation,
        currency=instance.currency, valid_from=now,
        notes="Automatically captured from edition pricing.",
    )


@receiver(post_save, sender=StockMovement)
@receiver(post_delete, sender=StockMovement)
def stock_movement_changed(sender, instance, **kwargs):
    rebuild_inventory_balance(instance.warehouse_id, instance.book_edition_id)


@receiver(post_save, sender=StockReservation)
@receiver(post_delete, sender=StockReservation)
def stock_reservation_changed(sender, instance, **kwargs):
    rebuild_inventory_balance(instance.warehouse_id, instance.book_edition_id)


@receiver(post_save, sender=BookOrderItem)
@receiver(post_delete, sender=BookOrderItem)
def order_item_changed(sender, instance, **kwargs):
    rebuild_order_totals(instance.order_id)


@receiver(post_save, sender=PaymentRecord)
def payment_saved(sender, instance, **kwargs):
    rebuild_order_totals(instance.order_id)
    sync_order_payment_to_ledger(instance)


@receiver(post_delete, sender=PaymentRecord)
def payment_deleted(sender, instance, **kwargs):
    rebuild_order_totals(instance.order_id)
    delete_order_payment_from_ledger(instance)


@receiver(post_save, sender=InboundShipmentItem)
@receiver(post_delete, sender=InboundShipmentItem)
def inbound_item_changed(sender, instance, **kwargs):
    instance.shipment.recalculate_totals(save=True)


@receiver(post_save, sender=InboundPayment)
def inbound_payment_saved(sender, instance, **kwargs):
    shipment = instance.shipment
    shipment.amount_paid = sum(
        (payment.amount for payment in shipment.payments.all()), Decimal("0.00")
    )
    shipment.recalculate_totals(save=True)
    sync_inbound_payment_to_ledger(instance)
    _refresh_inbound_schedule(
        getattr(instance, "_bookstore_previous_schedule_id", None)
    )
    _refresh_inbound_schedule(instance.schedule_id)


@receiver(post_delete, sender=InboundPayment)
def inbound_payment_deleted(sender, instance, **kwargs):
    shipment = instance.shipment
    shipment.amount_paid = sum(
        (payment.amount for payment in shipment.payments.all()), Decimal("0.00")
    )
    shipment.recalculate_totals(save=True)
    delete_inbound_payment_from_ledger(instance)
    _refresh_inbound_schedule(instance.schedule_id)

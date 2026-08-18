# apps/bookstore_inventory/services/reservations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.bookstore_inventory.constants import OrderStatus, ReservationStatus
from apps.bookstore_inventory.models import BookOrder, InventoryBalance, StockReservation
from apps.bookstore_inventory.services.balances import rebuild_inventory_balance
from apps.bookstore_inventory.services.access import (
    CAN_FULFILL_ORDERS, require_capability_for_warehouses,
)


@transaction.atomic
def reserve_book_order(order_id, user=None, expires_at=None):
    order = BookOrder.objects.select_for_update().prefetch_related("items").get(pk=order_id)
    if order.is_fulfilled or order.status == OrderStatus.CANCELLED:
        raise ValidationError("Fulfilled or cancelled orders cannot be reserved.")
    items = list(order.items.all())
    if not items:
        raise ValidationError("Cannot reserve an order without items.")
    require_capability_for_warehouses(
        user=user,
        warehouses=(item.warehouse for item in items),
        capability=CAN_FULFILL_ORDERS,
        permission="bookstore_inventory.reserve_bookorder",
    )

    for item in items:
        balance = InventoryBalance.objects.select_for_update().filter(
            warehouse=item.warehouse, book_edition=item.book_edition,
        ).first()
        existing = item.reservations.filter(status=ReservationStatus.ACTIVE).first()
        own_quantity = existing.quantity if existing else 0
        available = (balance.available_quantity if balance else 0) + own_quantity
        if available < item.quantity:
            raise ValidationError(
                f"Not enough available stock for '{item.book_edition}'. "
                f"Available: {available}, required: {item.quantity}."
            )

    created = []
    for item in items:
        item.reservations.filter(status=ReservationStatus.ACTIVE).update(
            status=ReservationStatus.RELEASED, active_order_item=None,
            closed_at=timezone.now()
        )
        reservation = StockReservation.objects.create(
            order_item=item, active_order_item=item, warehouse=item.warehouse,
            book_edition=item.book_edition, quantity=item.quantity,
            status=ReservationStatus.ACTIVE, reserved_at=timezone.now(),
            expires_at=expires_at, reserved_by=user or order.created_by,
        )
        rebuild_inventory_balance(item.warehouse_id, item.book_edition_id)
        created.append(reservation)
    order.status = OrderStatus.CONFIRMED
    order.save(update_fields=("status", "updated_at"))
    return created


@transaction.atomic
def release_book_order_reservations(order_id):
    reservations = list(StockReservation.objects.select_for_update().filter(
        order_item__order_id=order_id, status=ReservationStatus.ACTIVE,
    ))
    for reservation in reservations:
        reservation.status = ReservationStatus.RELEASED
        reservation.active_order_item = None
        reservation.closed_at = timezone.now()
        reservation.save(update_fields=(
            "status", "active_order_item", "closed_at", "updated_at",
        ))
        rebuild_inventory_balance(reservation.warehouse_id, reservation.book_edition_id)
    return len(reservations)

# apps/bookstore_inventory/services/inventory.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.bookstore_inventory.constants import (
    InventoryCondition, OrderStatus, OrderType, ReservationStatus, StockMovementType,
)
from apps.bookstore_inventory.models import (
    BookOrder, InboundShipment, InventoryBalance, InventoryLot,
    StockMovement,
)
from apps.bookstore_inventory.services.balances import rebuild_inventory_balance
from apps.bookstore_inventory.services.access import (
    CAN_FULFILL_ORDERS, CAN_RECEIVE_STOCK,
    require_capability_for_warehouses, require_warehouse_capability,
)
from apps.bookstore_inventory.services.numbering import generate_lot_number


def get_order_movement_type(order_type):
    return {
        OrderType.SALE: StockMovementType.SALE,
        OrderType.FREE_DISTRIBUTION: StockMovementType.GIFT,
        OrderType.DONATION_BASED: StockMovementType.DONATION_DISTRIBUTION,
        OrderType.INTERNAL_TRANSFER: StockMovementType.TRANSFER_OUT,
        OrderType.PROMOTIONAL: StockMovementType.GIFT,
    }.get(order_type, StockMovementType.OUT)


@transaction.atomic
def post_inbound_shipment_to_stock(shipment_id, user=None):
    shipment = InboundShipment.objects.select_for_update().prefetch_related(
        "items__book_edition", "items__location"
    ).get(pk=shipment_id)
    if shipment.is_stock_posted:
        raise ValidationError("This shipment has already been posted to stock.")
    require_warehouse_capability(
        user=user,
        warehouse=shipment.warehouse,
        capability=CAN_RECEIVE_STOCK,
        permission="bookstore_inventory.post_inboundshipment",
    )
    shipment.full_clean()
    items = list(shipment.items.all())
    if not items:
        raise ValidationError("Cannot post shipment without items.")
    payments = list(shipment.payments.all())
    schedules = list(shipment.payment_schedules.all())
    for payment in payments:
        payment.full_clean()
    for schedule in schedules:
        schedule.full_clean()
    if shipment.source_type == "donation" and (payments or schedules):
        raise ValidationError("Donation shipments cannot contain supplier payments or schedules.")
    paid_total = sum((payment.amount for payment in payments), 0)
    if shipment.total_cost > 0 and paid_total > shipment.total_cost:
        raise ValidationError("Recorded supplier payments exceed the shipment total.")
    scheduled_total = sum((schedule.amount for schedule in schedules), 0)
    if shipment.total_cost > 0 and scheduled_total > shipment.total_cost:
        raise ValidationError("Payment schedules exceed the shipment total.")

    created_movements = []
    for item in items:
        item.full_clean()
        lot = InventoryLot.objects.create(
            lot_number=item.lot_number or generate_lot_number(),
            warehouse=shipment.warehouse,
            location=item.location,
            book_edition=item.book_edition,
            source_item=item,
            condition=item.condition,
            received_at=shipment.received_at,
            unit_cost=item.unit_cost,
            currency=shipment.currency,
        )
        movement = StockMovement(
            warehouse=shipment.warehouse,
            location=item.location,
            book_edition=item.book_edition,
            lot=lot,
            inbound_shipment=shipment,
            movement_type=StockMovementType.IN,
            quantity=item.quantity,
            unit_price=item.unit_cost,
            total_amount=item.line_total,
            reference_type="inbound_shipment",
            reference_id=shipment.shipment_number,
            performed_by=user or shipment.created_by,
            performed_at=shipment.received_at or timezone.now(),
            notes=f"Posted from inbound shipment {shipment.shipment_number}",
        )
        movement.full_clean()
        movement.save()
        created_movements.append(movement)

    shipment.stock_posted_at = timezone.now()
    shipment.stock_posted_by = user or shipment.created_by
    shipment.save(update_fields=("stock_posted_at", "stock_posted_by", "updated_at"))
    return created_movements


def _movement_allocations(item):
    remaining = item.quantity
    allocations = []
    lots = InventoryLot.objects.select_for_update().filter(
        warehouse=item.warehouse,
        book_edition=item.book_edition,
        is_active=True,
        condition__in=(InventoryCondition.NEW, InventoryCondition.GOOD),
    ).order_by("received_at", "id")
    if item.location_id:
        lots = lots.filter(location_id=item.location_id)
    for lot in lots:
        quantity = min(remaining, max(lot.on_hand_quantity, 0))
        if quantity:
            allocations.append((lot, quantity))
            remaining -= quantity
        if remaining == 0:
            break
    if remaining:
        # Supports stock created before lot tracking was introduced.
        allocations.append((None, remaining))
    return allocations


@transaction.atomic
def fulfill_book_order(
    order_id,
    user=None,
    performed_at=None,
):
    operation_at = (
        performed_at
        or timezone.now()
    )

    if timezone.is_naive(operation_at):
        operation_at = timezone.make_aware(
            operation_at,
            timezone.get_current_timezone(),
        )

    order = (
        BookOrder.objects
        .select_for_update()
        .prefetch_related(
            "items__book_edition",
            "items__warehouse",
            "items__location",
            "items__reservations",
        )
        .get(pk=order_id)
    )

    if order.is_fulfilled:
        raise ValidationError(
            "This order has already been fulfilled."
        )

    if order.status == OrderStatus.CANCELLED:
        raise ValidationError(
            "Cancelled orders cannot be fulfilled."
        )

    items = list(
        order.items.all()
    )

    if not items:
        raise ValidationError(
            "Cannot fulfill an order without items."
        )

    require_capability_for_warehouses(
        user=user,
        warehouses=(
            item.warehouse
            for item in items
        ),
        capability=CAN_FULFILL_ORDERS,
        permission=(
            "bookstore_inventory."
            "fulfill_bookorder"
        ),
    )

    for item in items:
        balance = (
            InventoryBalance.objects
            .select_for_update()
            .filter(
                warehouse=item.warehouse,
                book_edition=item.book_edition,
            )
            .first()
        )

        reservation = (
            item.reservations
            .filter(
                status=ReservationStatus.ACTIVE
            )
            .first()
        )

        own_reserved = (
            reservation.quantity
            if reservation
            else 0
        )

        available_for_order = (
            (
                balance.available_quantity
                if balance
                else 0
            )
            + own_reserved
        )

        if available_for_order < item.quantity:
            raise ValidationError(
                f"Not enough stock for '{item.book_edition}'. "
                f"Available to this order: {available_for_order}, "
                f"required: {item.quantity}."
            )

    movement_type = get_order_movement_type(
        order.order_type
    )

    created_movements = []

    for item in items:
        for lot, quantity in _movement_allocations(
            item
        ):
            movement = StockMovement(
                warehouse=item.warehouse,
                location=(
                    item.location
                    or (
                        lot.location
                        if lot
                        else None
                    )
                ),
                book_edition=item.book_edition,
                lot=lot,
                movement_type=movement_type,
                quantity=quantity,
                unit_price=item.unit_price,
                total_amount=(
                    item.unit_price
                    * quantity
                ),
                reference_type="book_order",
                reference_id=order.order_number,
                performed_by=(
                    user
                    or order.created_by
                ),
                performed_at=operation_at,
                notes=(
                    f"Fulfilled from order "
                    f"{order.order_number}"
                ),
            )

            movement.full_clean()
            movement.save()

            created_movements.append(
                movement
            )

        item.reservations.filter(
            status=ReservationStatus.ACTIVE
        ).update(
            status=ReservationStatus.CONSUMED,
            active_order_item=None,
            closed_at=operation_at,
            updated_at=timezone.now(),
        )

        rebuild_inventory_balance(
            item.warehouse_id,
            item.book_edition_id,
        )

    order.status = OrderStatus.FULFILLED
    order.fulfilled_at = operation_at
    order.fulfilled_by = (
        user
        or order.created_by
    )

    order.save(
        update_fields=(
            "status",
            "fulfilled_at",
            "fulfilled_by",
            "updated_at",
        )
    )

    return created_movements
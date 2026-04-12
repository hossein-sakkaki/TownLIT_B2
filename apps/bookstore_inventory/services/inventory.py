# apps/bookstore_inventory/services/inventory.py

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.bookstore_inventory.constants import OrderStatus, OrderType, StockMovementType
from apps.bookstore_inventory.models import BookOrder, InboundShipment, InventoryBalance, StockMovement


def get_order_movement_type(order_type):
    # Map order type to stock movement type
    if order_type == OrderType.SALE:
        return StockMovementType.SALE
    if order_type == OrderType.FREE_DISTRIBUTION:
        return StockMovementType.GIFT
    if order_type == OrderType.DONATION_BASED:
        return StockMovementType.DONATION_DISTRIBUTION
    if order_type == OrderType.INTERNAL_TRANSFER:
        return StockMovementType.TRANSFER_OUT
    if order_type == OrderType.PROMOTIONAL:
        return StockMovementType.GIFT
    return StockMovementType.OUT


@transaction.atomic
def post_inbound_shipment_to_stock(shipment_id, user=None):
    # Post inbound shipment to stock once
    shipment = (
        InboundShipment.objects
        .select_for_update()
        .prefetch_related("items")
        .get(pk=shipment_id)
    )

    if shipment.is_stock_posted:
        raise ValidationError("This shipment has already been posted to stock.")

    items = list(shipment.items.all())
    if not items:
        raise ValidationError("Cannot post shipment without items.")

    created_movements = []
    for item in items:
        movement = StockMovement.objects.create(
            warehouse=shipment.warehouse,
            book_edition=item.book_edition,
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
        created_movements.append(movement)

    shipment.stock_posted_at = timezone.now()
    shipment.stock_posted_by = user or shipment.created_by
    shipment.save(update_fields=["stock_posted_at", "stock_posted_by", "updated_at"])

    return created_movements


@transaction.atomic
def fulfill_book_order(order_id, user=None):
    # Fulfill order and deduct stock once
    order = (
        BookOrder.objects
        .select_for_update()
        .prefetch_related("items__book_edition", "items__warehouse")
        .get(pk=order_id)
    )

    if order.is_fulfilled:
        raise ValidationError("This order has already been fulfilled.")

    if order.status == OrderStatus.CANCELLED:
        raise ValidationError("Cancelled orders cannot be fulfilled.")

    items = list(order.items.all())
    if not items:
        raise ValidationError("Cannot fulfill an order without items.")

    # Validate stock first
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

        available_quantity = balance.available_quantity if balance else 0
        if available_quantity < item.quantity:
            raise ValidationError(
                f"Not enough stock for '{item.book_edition}'. "
                f"Available: {available_quantity}, required: {item.quantity}."
            )

    # Create movements after validation
    movement_type = get_order_movement_type(order.order_type)
    created_movements = []

    for item in items:
        movement = StockMovement.objects.create(
            warehouse=item.warehouse,
            book_edition=item.book_edition,
            movement_type=movement_type,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_amount=item.line_total,
            reference_type="book_order",
            reference_id=order.order_number,
            performed_by=user or order.created_by,
            performed_at=timezone.now(),
            notes=f"Fulfilled from order {order.order_number}",
        )
        created_movements.append(movement)

    order.status = OrderStatus.FULFILLED
    order.fulfilled_at = timezone.now()
    order.fulfilled_by = user or order.created_by
    order.save(update_fields=["status", "fulfilled_at", "fulfilled_by", "updated_at"])

    return created_movements
# apps/bookstore_inventory/services/operations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, F, IntegerField, Sum, Value, When
from django.utils import timezone

from apps.bookstore_inventory.constants import (
    DocumentStatus, ReturnDirection, STOCK_IN_TYPES, STOCK_OUT_TYPES,
    StockCountStatus, StockMovementType, TransferStatus,
)
from apps.bookstore_inventory.models import (
    InventoryBalance, InventoryLot, StockAdjustment, StockCount,
    StockMovement, StockReturn, StockTransfer,
)
from apps.bookstore_inventory.services.numbering import generate_lot_number
from apps.bookstore_inventory.services.access import (
    CAN_ADJUST_STOCK, CAN_COUNT_STOCK, CAN_PROCESS_RETURNS,
    CAN_TRANSFER_STOCK, require_warehouse_capability,
)


def _quantity_at(*, warehouse_id, book_edition_id, location_id=None, lot_id=None):
    queryset = StockMovement.objects.filter(
        warehouse_id=warehouse_id, book_edition_id=book_edition_id,
    )
    if location_id is not None:
        queryset = queryset.filter(location_id=location_id)
    if lot_id is not None:
        queryset = queryset.filter(lot_id=lot_id)
    return queryset.aggregate(
        total=Sum(Case(
            When(movement_type__in=STOCK_IN_TYPES, then="quantity"),
            When(movement_type__in=STOCK_OUT_TYPES, then=-F("quantity")),
            default=Value(0), output_field=IntegerField(),
        ))
    )["total"] or 0
@transaction.atomic
def dispatch_stock_transfer(transfer_id, user=None):
    transfer = StockTransfer.objects.select_for_update().prefetch_related(
        "items__book_edition", "items__source_lot", "items__source_location"
    ).get(pk=transfer_id)
    if transfer.status != TransferStatus.DRAFT:
        raise ValidationError("Only a draft transfer can be dispatched.")
    require_warehouse_capability(
        user=user,
        warehouse=transfer.from_warehouse,
        capability=CAN_TRANSFER_STOCK,
        permission="bookstore_inventory.dispatch_stocktransfer",
    )
    items = list(transfer.items.all())
    if not items:
        raise ValidationError("Cannot dispatch a transfer without items.")
    for item in items:
        item.full_clean()
        balance = InventoryBalance.objects.select_for_update().filter(
            warehouse=transfer.from_warehouse, book_edition=item.book_edition,
        ).first()
        if not balance or balance.available_quantity < item.quantity:
            raise ValidationError(f"Insufficient available stock for '{item.book_edition}'.")
        if item.source_lot_id and item.source_lot.on_hand_quantity < item.quantity:
            raise ValidationError(f"Insufficient stock in lot {item.source_lot}.")
    now = timezone.now()
    for item in items:
        StockMovement.objects.create(
            warehouse=transfer.from_warehouse, location=item.source_location,
            book_edition=item.book_edition, lot=item.source_lot,
            movement_type=StockMovementType.TRANSFER_OUT, quantity=item.quantity,
            reference_type="stock_transfer", reference_id=transfer.transfer_number,
            performed_by=user or transfer.created_by, performed_at=now,
            notes=f"Dispatched transfer {transfer.transfer_number}",
        )
    transfer.status = TransferStatus.DISPATCHED
    transfer.dispatched_at = now
    transfer.dispatched_by = user or transfer.created_by
    transfer.save(update_fields=("status", "dispatched_at", "dispatched_by", "updated_at"))
    return transfer


@transaction.atomic
def receive_stock_transfer(transfer_id, user=None):
    transfer = StockTransfer.objects.select_for_update().prefetch_related(
        "items__book_edition", "items__source_lot", "items__destination_location"
    ).get(pk=transfer_id)
    if transfer.status != TransferStatus.DISPATCHED:
        raise ValidationError("Only a dispatched transfer can be received.")
    require_warehouse_capability(
        user=user,
        warehouse=transfer.to_warehouse,
        capability=CAN_TRANSFER_STOCK,
        permission="bookstore_inventory.receive_stocktransfer",
    )
    now = timezone.now()
    for item in transfer.items.all():
        quantity = item.received_quantity or item.quantity
        lot = InventoryLot.objects.create(
            lot_number=generate_lot_number(), warehouse=transfer.to_warehouse,
            location=item.destination_location, book_edition=item.book_edition,
            condition=(item.source_lot.condition if item.source_lot else "good"),
            received_at=now,
            unit_cost=(item.source_lot.unit_cost if item.source_lot else 0),
            currency=(item.source_lot.currency if item.source_lot else "CAD"),
            notes=f"Received from transfer {transfer.transfer_number}",
        )
        StockMovement.objects.create(
            warehouse=transfer.to_warehouse, location=item.destination_location,
            book_edition=item.book_edition, lot=lot,
            movement_type=StockMovementType.TRANSFER_IN, quantity=quantity,
            reference_type="stock_transfer", reference_id=transfer.transfer_number,
            performed_by=user or transfer.created_by, performed_at=now,
            notes=f"Received transfer {transfer.transfer_number}",
        )
        if not item.received_quantity:
            item.received_quantity = quantity
            item.save(update_fields=("received_quantity", "updated_at"))
    transfer.status = TransferStatus.RECEIVED
    transfer.received_at = now
    transfer.received_by = user or transfer.created_by
    transfer.save(update_fields=("status", "received_at", "received_by", "updated_at"))
    return transfer


@transaction.atomic
def snapshot_stock_count(stock_count_id, user=None):
    stock_count = StockCount.objects.select_for_update().prefetch_related("items").get(pk=stock_count_id)
    if stock_count.status not in {StockCountStatus.DRAFT, StockCountStatus.COUNTING}:
        raise ValidationError("Only a draft count can be prepared.")
    require_warehouse_capability(
        user=user,
        warehouse=stock_count.warehouse,
        capability=CAN_COUNT_STOCK,
        permission="bookstore_inventory.snapshot_stockcount",
    )
    for item in stock_count.items.all():
        item.expected_quantity = _quantity_at(
            warehouse_id=stock_count.warehouse_id,
            book_edition_id=item.book_edition_id,
            location_id=stock_count.location_id,
            lot_id=item.lot_id,
        )
        item.save(update_fields=("expected_quantity", "updated_at"))
    stock_count.status = StockCountStatus.COUNTING
    stock_count.counted_by = user or stock_count.created_by
    stock_count.counted_at = timezone.now()
    stock_count.save(update_fields=("status", "counted_by", "counted_at", "updated_at"))
    return stock_count


@transaction.atomic
def post_stock_count(stock_count_id, user=None):
    stock_count = StockCount.objects.select_for_update().prefetch_related("items").get(pk=stock_count_id)
    if stock_count.status not in {StockCountStatus.COUNTING, StockCountStatus.SUBMITTED}:
        raise ValidationError("Only a counted or submitted stock count can be posted.")
    require_warehouse_capability(
        user=user,
        warehouse=stock_count.warehouse,
        capability=CAN_COUNT_STOCK,
        permission="bookstore_inventory.post_stockcount",
    )
    items = list(stock_count.items.all())
    if not items:
        raise ValidationError("Cannot post a stock count without items.")
    now = timezone.now()
    for item in items:
        variance = item.variance
        if variance == 0:
            continue
        StockMovement.objects.create(
            warehouse=stock_count.warehouse, location=stock_count.location,
            book_edition=item.book_edition, lot=item.lot,
            movement_type=(
                StockMovementType.ADJUSTMENT_PLUS if variance > 0
                else StockMovementType.ADJUSTMENT_MINUS
            ),
            quantity=abs(variance), reference_type="stock_count",
            reference_id=stock_count.count_number,
            performed_by=user or stock_count.created_by, performed_at=now,
            notes=f"Stock-count variance: {item.get_reason_display()}. {item.notes}",
        )
    stock_count.status = StockCountStatus.POSTED
    stock_count.posted_at = now
    stock_count.posted_by = user or stock_count.created_by
    stock_count.save(update_fields=("status", "posted_at", "posted_by", "updated_at"))
    return stock_count


@transaction.atomic
def post_stock_adjustment(adjustment_id, user=None):
    adjustment = StockAdjustment.objects.select_for_update().prefetch_related("items").get(pk=adjustment_id)
    if adjustment.status != DocumentStatus.DRAFT:
        raise ValidationError("Only a draft adjustment can be posted.")
    require_warehouse_capability(
        user=user,
        warehouse=adjustment.warehouse,
        capability=CAN_ADJUST_STOCK,
        permission="bookstore_inventory.post_stockadjustment",
    )
    items = list(adjustment.items.all())
    if not items:
        raise ValidationError("Cannot post an adjustment without items.")
    now = timezone.now()
    for item in items:
        item.full_clean()
        if item.quantity_delta < 0:
            balance = InventoryBalance.objects.select_for_update().filter(
                warehouse=adjustment.warehouse, book_edition=item.book_edition,
            ).first()
            if not balance or balance.available_quantity < abs(item.quantity_delta):
                raise ValidationError(f"Insufficient stock for '{item.book_edition}'.")
        movement_type = StockMovementType.ADJUSTMENT_PLUS
        if item.quantity_delta < 0:
            movement_type = {
                "damage": StockMovementType.DAMAGED,
                "loss": StockMovementType.LOST,
            }.get(adjustment.reason, StockMovementType.ADJUSTMENT_MINUS)
        StockMovement.objects.create(
            warehouse=adjustment.warehouse, location=item.location,
            book_edition=item.book_edition, lot=item.lot,
            movement_type=movement_type, quantity=abs(item.quantity_delta),
            reference_type="stock_adjustment", reference_id=adjustment.adjustment_number,
            performed_by=user or adjustment.created_by, performed_at=now,
            notes=f"{adjustment.get_reason_display()}: {item.notes}",
        )
    adjustment.status = DocumentStatus.POSTED
    adjustment.posted_at = now
    adjustment.posted_by = user or adjustment.created_by
    adjustment.save(update_fields=("status", "posted_at", "posted_by", "updated_at"))
    return adjustment


@transaction.atomic
def post_stock_return(stock_return_id, user=None):
    stock_return = StockReturn.objects.select_for_update().prefetch_related("items").get(pk=stock_return_id)
    if stock_return.status != DocumentStatus.DRAFT:
        raise ValidationError("Only a draft return can be posted.")
    require_warehouse_capability(
        user=user,
        warehouse=stock_return.warehouse,
        capability=CAN_PROCESS_RETURNS,
        permission="bookstore_inventory.post_stockreturn",
    )
    stock_return.full_clean()
    items = list(stock_return.items.all())
    if not items:
        raise ValidationError("Cannot post a return without items.")
    now = timezone.now()
    is_inbound = stock_return.direction == ReturnDirection.CUSTOMER_TO_STOCK
    for item in items:
        item.full_clean()
        if not is_inbound:
            balance = InventoryBalance.objects.select_for_update().filter(
                warehouse=stock_return.warehouse, book_edition=item.book_edition,
            ).first()
            if not balance or balance.available_quantity < item.quantity:
                raise ValidationError(f"Insufficient stock for '{item.book_edition}'.")
        lot = item.lot
        if is_inbound and lot is None:
            lot = InventoryLot.objects.create(
                lot_number=generate_lot_number(), warehouse=stock_return.warehouse,
                location=item.location, book_edition=item.book_edition,
                condition=item.condition, received_at=now,
                notes=f"Customer return {stock_return.return_number}",
            )
        StockMovement.objects.create(
            warehouse=stock_return.warehouse, location=item.location,
            book_edition=item.book_edition, lot=lot,
            movement_type=(StockMovementType.RETURN_IN if is_inbound else StockMovementType.RETURN_OUT),
            quantity=item.quantity, reference_type="stock_return",
            reference_id=stock_return.return_number,
            performed_by=user or stock_return.created_by, performed_at=now,
            notes=f"Posted return {stock_return.return_number}",
        )
    stock_return.status = DocumentStatus.POSTED
    stock_return.posted_at = now
    stock_return.posted_by = user or stock_return.created_by
    stock_return.save(update_fields=("status", "posted_at", "posted_by", "updated_at"))
    return stock_return

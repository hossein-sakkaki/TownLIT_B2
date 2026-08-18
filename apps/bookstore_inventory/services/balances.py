# apps/bookstore_inventory/services/balances.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.db.models import Case, F, IntegerField, Sum, Value, When

from apps.bookstore_inventory.constants import (
    InventoryCondition, ReservationStatus, STOCK_IN_TYPES, STOCK_OUT_TYPES,
)
from apps.bookstore_inventory.models import InventoryBalance, StockMovement, StockReservation


def rebuild_inventory_balance(warehouse_id, book_edition_id):
    on_hand = StockMovement.calculate_on_hand(warehouse_id, book_edition_id)
    unavailable_conditions = (
        InventoryCondition.DAMAGED, InventoryCondition.DISPLAY,
        InventoryCondition.QUARANTINED, InventoryCondition.UNSELLABLE,
    )
    unavailable = StockMovement.objects.filter(
        warehouse_id=warehouse_id,
        book_edition_id=book_edition_id,
        lot__condition__in=unavailable_conditions,
    ).aggregate(total=Sum(Case(
        When(movement_type__in=STOCK_IN_TYPES, then=F("quantity")),
        When(movement_type__in=STOCK_OUT_TYPES, then=-F("quantity")),
        default=Value(0), output_field=IntegerField(),
    )))["total"] or 0
    reserved = StockReservation.objects.filter(
        warehouse_id=warehouse_id,
        book_edition_id=book_edition_id,
        status=ReservationStatus.ACTIVE,
    ).aggregate(total=Sum("quantity"))["total"] or 0
    balance, _ = InventoryBalance.objects.get_or_create(
        warehouse_id=warehouse_id,
        book_edition_id=book_edition_id,
        defaults={
            "on_hand_quantity": 0, "reserved_quantity": 0,
            "unavailable_quantity": 0,
        },
    )
    balance.on_hand_quantity = on_hand
    balance.reserved_quantity = reserved
    balance.unavailable_quantity = max(unavailable, 0)
    balance.save(update_fields=(
        "on_hand_quantity", "reserved_quantity", "unavailable_quantity", "updated_at",
    ))
    return balance

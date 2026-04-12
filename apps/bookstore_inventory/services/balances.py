# apps/bookstore_inventory/services/balances.py

from apps.bookstore_inventory.models import InventoryBalance, StockMovement


def rebuild_inventory_balance(warehouse_id, book_edition_id):
    # Recalculate balance from movement history
    on_hand = StockMovement.calculate_on_hand(
        warehouse_id=warehouse_id,
        book_edition_id=book_edition_id,
    )

    balance, _ = InventoryBalance.objects.get_or_create(
        warehouse_id=warehouse_id,
        book_edition_id=book_edition_id,
        defaults={
            "on_hand_quantity": 0,
            "reserved_quantity": 0,
        },
    )

    balance.on_hand_quantity = on_hand
    balance.save(update_fields=["on_hand_quantity", "updated_at"])
    return balance
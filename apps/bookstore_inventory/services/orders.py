# apps/bookstore_inventory/services/orders.py

from apps.bookstore_inventory.models import BookOrder


def rebuild_order_totals(order_id):
    # Recalculate order totals
    order = BookOrder.objects.get(pk=order_id)
    order.recalculate_totals(save=True)
    return order
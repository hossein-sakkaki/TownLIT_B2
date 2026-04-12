# apps/bookstore_inventory/admin/actions.py

from django.contrib import messages
from django.core.exceptions import ValidationError

from apps.bookstore_inventory.services.inventory import fulfill_book_order, post_inbound_shipment_to_stock


def post_selected_shipments_to_stock(modeladmin, request, queryset):
    # Post inbound shipments to stock
    success_count = 0

    for shipment in queryset:
        try:
            post_inbound_shipment_to_stock(
                shipment_id=shipment.pk,
                user=request.user,
            )
            success_count += 1
        except ValidationError as exc:
            modeladmin.message_user(
                request,
                f"Shipment {shipment.shipment_number}: {exc}",
                level=messages.ERROR,
            )

    if success_count:
        modeladmin.message_user(
            request,
            f"{success_count} shipment(s) posted to stock successfully.",
            level=messages.SUCCESS,
        )


post_selected_shipments_to_stock.short_description = "Post selected shipments to stock"


def fulfill_selected_orders(modeladmin, request, queryset):
    # Fulfill orders and deduct stock
    success_count = 0

    for order in queryset:
        try:
            fulfill_book_order(
                order_id=order.pk,
                user=request.user,
            )
            success_count += 1
        except ValidationError as exc:
            modeladmin.message_user(
                request,
                f"Order {order.order_number}: {exc}",
                level=messages.ERROR,
            )

    if success_count:
        modeladmin.message_user(
            request,
            f"{success_count} order(s) fulfilled successfully.",
            level=messages.SUCCESS,
        )


fulfill_selected_orders.short_description = "Fulfill selected orders and deduct stock"
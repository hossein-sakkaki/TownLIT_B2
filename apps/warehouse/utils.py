
from django.utils import timezone
from apps.orders.models import OrderItem
from .models import TemporaryReservation
from apps.config.warehouse_constans import TEMPORARY_RESERVATION_DURATION



# Logic for creating a temporary reservation -----------------------------
def create_temporary_reservation(order_item, reserved_quantity):
    expiry_date = timezone.now() + TEMPORARY_RESERVATION_DURATION
    reservation = TemporaryReservation.objects.create(
        order_item=order_item,
        reserved_quantity=reserved_quantity,
        expiry_date=expiry_date
    )
    return reservation
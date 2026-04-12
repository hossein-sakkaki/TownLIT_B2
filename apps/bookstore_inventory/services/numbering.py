# apps/bookstore_inventory/services/numbering.py

from uuid import uuid4

from django.utils import timezone


def generate_shipment_number():
    # Generate shipment number
    stamp = timezone.now().strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:4].upper()
    return f"INB-{stamp}-{suffix}"


def generate_order_number():
    # Generate order number
    stamp = timezone.now().strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:4].upper()
    return f"ORD-{stamp}-{suffix}"
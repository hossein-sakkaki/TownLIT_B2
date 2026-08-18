# apps/bookstore_inventory/services/numbering.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from uuid import uuid4

from django.utils import timezone


def _number(prefix):
    stamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid4().hex[:8].upper()}"


def generate_shipment_number():
    return _number("INB")


def generate_order_number():
    return _number("ORD")


def generate_transfer_number():
    return _number("TRF")


def generate_stock_count_number():
    return _number("CNT")


def generate_adjustment_number():
    return _number("ADJ")


def generate_return_number():
    return _number("RTN")


def generate_lot_number():
    return _number("LOT")

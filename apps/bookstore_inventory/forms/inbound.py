# apps/bookstore_inventory/forms/inbound.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from decimal import Decimal

from django import forms

from apps.bookstore_inventory.constants import (
    InboundPaymentStatus, InboundSourceType,
)
from apps.bookstore_inventory.models import InboundShipment


class InboundShipmentAdminForm(forms.ModelForm):
    class Meta:
        model = InboundShipment
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "shipment_number" in self.fields:
            self.fields["shipment_number"].required = False
            self.fields["shipment_number"].help_text = (
                "Leave blank to generate a permanent inbound number automatically."
            )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("source_type") == InboundSourceType.DONATION:
            self.instance.payment_status = InboundPaymentStatus.NOT_REQUIRED
        for field in ("shipping_cost", "other_cost"):
            value = cleaned.get(field)
            if value is not None and value < Decimal("0"):
                self.add_error(field, "Cost cannot be negative.")
        if cleaned.get("supplier") and not cleaned.get("supplier_name"):
            cleaned["supplier_name"] = str(cleaned["supplier"])
        if cleaned.get("donor") and not cleaned.get("donor_name"):
            cleaned["donor_name"] = str(cleaned["donor"])
        return cleaned

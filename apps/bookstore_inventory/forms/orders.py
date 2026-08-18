# apps/bookstore_inventory/forms/orders.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django import forms

from apps.bookstore_inventory.constants import DeliveryMethod, RecipientType
from apps.bookstore_inventory.models import BookOrder


class BookOrderAdminForm(forms.ModelForm):
    class Meta:
        model = BookOrder
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "order_number" in self.fields:
            self.fields["order_number"].required = False
            self.fields["order_number"].help_text = (
                "Leave blank to generate a permanent order number automatically."
            )
        help_texts = {
            "recipient_type": "Choose a person or an organization; complete only the matching section.",
            "recipient_first_name": "Person orders only.",
            "recipient_last_name": "Person orders only.",
            "recipient_email": "Optional; collect only what operations need.",
            "recipient_phone": "Optional; collect only what operations need.",
            "recipient_organization": "Choose the organization once; its name is preserved as a snapshot on this order.",
            "organization_name": "Historical snapshot; use only when the organization is not yet in the directory.",
            "organization_contact_person": "Optional contact inside the organization.",
            "delivery_method": "Shipping requires address line 1.",
            "purpose": "Used in distribution reporting.",
            "address_line_1": "Required for shipping; otherwise optional.",
        }
        for name, help_text in help_texts.items():
            if name in self.fields:
                self.fields[name].help_text = help_text

    def clean(self):
        cleaned = super().clean()
        person_fields = ("recipient_first_name", "recipient_last_name", "recipient_email", "recipient_phone")
        organization_fields = (
            "recipient_organization", "organization_name",
            "organization_contact_person",
            "organization_email",
            "organization_phone",
        )

        def value(name):
            raw = cleaned.get(name)
            return raw.strip() if isinstance(raw, str) else raw

        recipient_type = cleaned.get("recipient_type")
        if recipient_type == RecipientType.PERSON:
            if not any(value(name) for name in person_fields):
                raise forms.ValidationError("Enter at least one person name, email, or phone.")
            for name in organization_fields:
                if value(name):
                    self.add_error(name, "Leave this empty for a person order.")
        elif recipient_type == RecipientType.ORGANIZATION:
            if not value("recipient_organization") and not value("organization_name"):
                self.add_error("recipient_organization", "Choose an organization or provide a snapshot name.")
            for name in person_fields:
                if value(name):
                    self.add_error(name, "Leave this empty for an organization order.")

        if cleaned.get("delivery_method") == DeliveryMethod.SHIPPING and not value("address_line_1"):
            self.add_error("address_line_1", "Address line 1 is required for shipping.")
        return cleaned

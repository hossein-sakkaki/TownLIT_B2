# apps/bookstore_inventory/forms/orders.py

from django import forms

from apps.bookstore_inventory.constants import DeliveryMethod, RecipientType
from apps.bookstore_inventory.models import BookOrder


class BookOrderAdminForm(forms.ModelForm):
    # Admin form for smarter recipient handling

    class Meta:
        model = BookOrder
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        # Configure admin-friendly labels and help texts
        super().__init__(*args, **kwargs)

        self.fields["recipient_type"].help_text = "Choose whether this outgoing order is for a person or an organization."
        self.fields["recipient_first_name"].help_text = "Optional. Use only when the recipient is a person."
        self.fields["recipient_last_name"].help_text = "Optional. Use only when the recipient is a person."
        self.fields["recipient_email"].help_text = "Optional. Keep personal data minimal."
        self.fields["recipient_phone"].help_text = "Optional. Keep personal data minimal."

        self.fields["organization_name"].help_text = "Required for organization orders."
        self.fields["organization_contact_person"].help_text = "Optional contact person inside the organization."
        self.fields["organization_email"].help_text = "Optional."
        self.fields["organization_phone"].help_text = "Optional."

        self.fields["delivery_method"].help_text = "Select how the books were delivered."
        self.fields["purpose"].help_text = "Select the purpose of this outgoing order."

        self.fields["address_line_1"].help_text = "Required only for shipping."
        self.fields["address_line_2"].help_text = "Optional."
        self.fields["city"].help_text = "Optional unless shipping needs an address."
        self.fields["province_state"].help_text = "Optional unless shipping needs an address."
        self.fields["postal_code"].help_text = "Optional unless shipping needs an address."
        self.fields["country"].help_text = "Optional unless shipping needs an address."

    def clean(self):
        # Server-side validation for recipient and delivery logic
        cleaned_data = super().clean()

        recipient_type = cleaned_data.get("recipient_type")
        delivery_method = cleaned_data.get("delivery_method")

        recipient_first_name = cleaned_data.get("recipient_first_name", "").strip()
        recipient_last_name = cleaned_data.get("recipient_last_name", "").strip()
        recipient_email = cleaned_data.get("recipient_email", "").strip()
        recipient_phone = cleaned_data.get("recipient_phone", "").strip()

        organization_name = cleaned_data.get("organization_name", "").strip()
        organization_contact_person = cleaned_data.get("organization_contact_person", "").strip()
        organization_email = cleaned_data.get("organization_email", "").strip()
        organization_phone = cleaned_data.get("organization_phone", "").strip()

        address_line_1 = cleaned_data.get("address_line_1", "").strip()

        if recipient_type == RecipientType.PERSON:
            # Organization fields should stay empty for person orders
            if organization_name:
                self.add_error("organization_name", "Leave this empty for person orders.")
            if organization_contact_person:
                self.add_error("organization_contact_person", "Leave this empty for person orders.")
            if organization_email:
                self.add_error("organization_email", "Leave this empty for person orders.")
            if organization_phone:
                self.add_error("organization_phone", "Leave this empty for person orders.")

            # At least one lightweight identifier is helpful
            if not any([recipient_first_name, recipient_last_name, recipient_email, recipient_phone]):
                raise forms.ValidationError(
                    "For person orders, enter at least one of these: first name, last name, email, or phone."
                )

        if recipient_type == RecipientType.ORGANIZATION:
            if not organization_name:
                self.add_error("organization_name", "Organization name is required for organization orders.")

            # Person fields should stay empty for organization orders
            if recipient_first_name:
                self.add_error("recipient_first_name", "Leave this empty for organization orders.")
            if recipient_last_name:
                self.add_error("recipient_last_name", "Leave this empty for organization orders.")
            if recipient_email:
                self.add_error("recipient_email", "Leave this empty for organization orders.")
            if recipient_phone:
                self.add_error("recipient_phone", "Leave this empty for organization orders.")

        if delivery_method == DeliveryMethod.SHIPPING and not address_line_1:
            self.add_error("address_line_1", "Address line 1 is required for shipping.")

        return cleaned_data
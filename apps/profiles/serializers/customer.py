from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.profiles.models.customer import Customer
from apps.accounts.serializers.address_serializers import AddressSerializer

CustomUser = get_user_model()


class CustomerSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())
    billing_address = AddressSerializer(read_only=True)
    shipping_addresses = AddressSerializer(many=True, read_only=True)
    customer_phone_number = serializers.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r"^\+?1?\d{9,15}$",
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
            )
        ],
    )

    class Meta:
        model = Customer
        fields = [
            "user",
            "billing_address",
            "shipping_addresses",
            "customer_phone_number",
            "register_date",
            "deactivation_reason",
            "deactivation_note",
            "is_active",
        ]
        read_only_fields = ["user", "register_date", "is_active"]

    def validate_shipping_addresses(self, value):
        if not value:
            raise serializers.ValidationError("Shipping addresses cannot be empty.")
        return value
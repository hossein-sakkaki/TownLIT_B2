# apps/profiles/models/customer.py

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.accounts.models.address import Address
from apps.profiles.constants.customer import CUSTOMER_DEACTIVATION_REASON_CHOICES
from utils.common.utils import SlugMixin
from validators.user_validators import validate_phone_number

CustomUser = get_user_model()


class Customer(SlugMixin):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="customer_profile",
        verbose_name="User",
    )
    billing_address = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_billing_addresses",
        verbose_name="Billing Address",
    )
    shipping_addresses = models.ManyToManyField(
        Address,
        related_name="customer_shipping_addresses",
        verbose_name="Shipping Addresses",
    )
    customer_phone_number = models.CharField(
        max_length=20,
        validators=[validate_phone_number],
        verbose_name="Phone Number",
    )
    register_date = models.DateField(default=timezone.now, verbose_name="Register Date")
    deactivation_reason = models.CharField(
        max_length=50,
        choices=CUSTOMER_DEACTIVATION_REASON_CHOICES,
        null=True,
        blank=True,
        verbose_name="Deactivation Reason",
    )
    deactivation_note = models.TextField(null=True, blank=True, verbose_name="Deactivation Note")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    url_name = "customer_detail"

    class Meta:
        verbose_name = "5. Customer"
        verbose_name_plural = "5. Customers"

    def __str__(self):
        shipping_address = self.shipping_addresses.first()
        return (
            f"{self.user.username} - Shipping Address: "
            f"{shipping_address if shipping_address else 'No shipping address'}"
        )

    def get_slug_source(self):
        return self.user.username
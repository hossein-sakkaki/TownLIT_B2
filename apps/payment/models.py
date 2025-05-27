from django.db import models
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4
from django.conf import settings

from apps.profilesOrg.models import Organization
from apps.orders.models import ShoppingCart, Order
from apps.accounts.models import Address
from apps.payment.constants import (
                                    PAYMENT_STATUS_CHOICES, PENDING,
                                    PRICING_TYPE_CHOICES, DURATION_CHOICES, BILLING_CYCLE_CHOICES
                                )
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# PRICING MODEL --------------------------------------------------------------
class Pricing(models.Model):
    id = models.BigAutoField(primary_key=True)
    pricing_type = models.CharField(max_length=20, choices=PRICING_TYPE_CHOICES, verbose_name='Pricing Type')
    duration = models.CharField(max_length=20, choices=DURATION_CHOICES, verbose_name='Duration')
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES, verbose_name='Billing Cycle')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Price')
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Discount (%)')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    class Meta:
        verbose_name = "Pricing"
        verbose_name_plural = "Pricings"
        unique_together = ['pricing_type', 'duration', 'billing_cycle']

    def __str__(self):
        return f"{self.pricing_type} - {self.duration} - {self.billing_cycle} - {self.price}"
    

# PAYMENT MODEL ------------------------------------------------------------------------------------------
class Payment(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name='payments', verbose_name='User')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='payments', verbose_name='Organization')
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Amount')
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default=PENDING, verbose_name='Payment Status')
    is_anonymous_donor = models.BooleanField(default=False, verbose_name='Anonymous Donor')
    email = models.EmailField(null=True, blank=True, verbose_name='Guest Email')

    created_at = models.DateTimeField(default=timezone.now, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')
    description = models.TextField(null=True, blank=True, verbose_name='Description')
    reference_number = models.CharField(max_length=30, unique=True, editable=False, verbose_name='Reference Number')
    
    cancel_token = models.CharField(max_length=64, null=True, blank=True, unique=True)
    cancel_token_created_at = models.DateTimeField(null=True, blank=True)
    confirm_token = models.CharField(max_length=64, null=True, blank=True, unique=True)
    confirm_token_created_at = models.DateTimeField(null=True, blank=True)

    def is_valid_cancel_token(self, token: str) -> bool:
        if not self.cancel_token or not self.cancel_token_created_at:
            return False

        if self.cancel_token != token:
            return False

        expiration_minutes = getattr(
            settings,
            'TOWNLIT_PAYMENT_CANCEL_TOKEN_EXPIRATION_MINUTES',
            15
        )
        expiration_time = self.cancel_token_created_at + timedelta(minutes=expiration_minutes)

        return timezone.now() <= expiration_time

    def is_valid_confirm_token(self, token: str) -> bool:
        """
        Validates the provided token against stored confirm_token and checks expiration.
        """
        if not self.confirm_token or not self.confirm_token_created_at:
            return False

        if self.confirm_token != token:
            return False

        expiration_minutes = getattr(
            settings,
            'TOWNLIT_PAYMENT_CONFIRM_TOKEN_EXPIRATION_MINUTES',
            10
        )
        expiration_time = self.confirm_token_created_at + timedelta(minutes=expiration_minutes)

        return timezone.now() <= expiration_time

    def save(self, *args, **kwargs):
        if not self.reference_number:
            self.reference_number = str(uuid4()).replace('-', '').upper()[:10]
        super().save(*args, **kwargs)
        
    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        user_display = self.user.username if self.user else "Anonymous"
        return f"{user_display} - ${self.amount}"



# PAYMENT DONATION MODEL ------------------------------------------------------------------------------
class PaymentDonation(Payment):
    message = models.TextField(null=True, blank=True, verbose_name='Message')

    class Meta:
        verbose_name = "Payment Donation"
        verbose_name_plural = "Payment Donations"

    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        return f"{username} - Donation - {self.amount}"


# PAYMENT SUBSCRIPTION MODEL -----------------------------------------------------------------------------
class PaymentSubscription(Payment):
    subscription_pricing = models.ForeignKey(Pricing, on_delete=models.PROTECT, verbose_name='Subscription Pricing')
    start_date = models.DateField(default=timezone.now, verbose_name='Start Date')
    end_date = models.DateField(null=True, blank=True, verbose_name='End Date')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    class Meta:
        verbose_name = "Payment Subscription"
        verbose_name_plural = "Payment Subscriptions"

    def __str__(self):
        return f"{self.user.username} - {self.subscription_pricing.subscription_type} Subscription"


# PAYMENT ADVERTISEMENT MODEL -------------------------------------------------------------------------
class PaymentAdvertisement(Payment):
    advertisement_pricing = models.ForeignKey(Pricing, on_delete=models.PROTECT, verbose_name='Advertisement Pricing')
    start_date = models.DateField(default=timezone.now, verbose_name='Start Date')
    end_date = models.DateField(null=True, blank=True, verbose_name='End Date')

    class Meta:
        verbose_name = "Payment Advertisement"
        verbose_name_plural = "Payment Advertisements"

    def __str__(self):
        return f"{self.user.username} - {self.advertisement_pricing.advertisement_type} Advertisement"
    


# PAYMENT SHOPPING CART MODEL -------------------------------------------------------------------------
class PaymentShoppingCart(Payment):
    shopping_cart = models.OneToOneField(ShoppingCart, on_delete=models.PROTECT, related_name='payment', verbose_name='Shopping Cart')
    billing_address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True, blank=True, verbose_name='Billing Address')

    def save(self, *args, **kwargs):
        if self.shopping_cart and not self.billing_address:
            order = Order.objects.filter(shopping_cart=self.shopping_cart).first()
            if order:
                self.billing_address = order.billing_address
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Payment Shopping Cart"
        verbose_name_plural = "Payment Shopping Carts"

    def __str__(self):
        return f"{self.user.username} - Shopping Cart Payment - {self.amount}"


# PAYMENT INVOICE MODEL ------------------------------------------------------------------------------
class PaymentInvoice(models.Model):
    id = models.BigAutoField(primary_key=True)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='invoice', verbose_name='Payment')
    invoice_number = models.CharField(max_length=30, unique=True, editable=False, verbose_name='Invoice Number')
    issued_date = models.DateTimeField(default=timezone.now, verbose_name='Issued Date')
    due_date = models.DateTimeField(null=True, blank=True, verbose_name='Due Date')
    is_paid = models.BooleanField(default=False, verbose_name='Is Paid')

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.payment.reference_number
        super().save(*args, **kwargs)
        
    class Meta:
        verbose_name = "Payment Invoice"
        verbose_name_plural = "Payment Invoices"

    def __str__(self):
        return f"Invoice #{self.invoice_number} for Payment ID {self.payment.id}"
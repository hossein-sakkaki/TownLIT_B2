from django.contrib import admin
from .models import Pricing, Payment, PaymentSubscription, PaymentAdvertisement, PaymentDonation, PaymentShoppingCart, PaymentInvoice




# PRICING Admin -------------------------------------------------------------------
@admin.register(Pricing)
class PricingAdmin(admin.ModelAdmin):
    list_display = ('pricing_type', 'duration', 'billing_cycle', 'price', 'discount', 'is_active')
    list_filter = ('pricing_type', 'duration', 'billing_cycle', 'is_active')
    search_fields = ('pricing_type', 'duration', 'billing_cycle')
    list_editable = ('price', 'discount', 'is_active')


# PAYMENT Admin -------------------------------------------------------------------
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'amount', 'payment_status', 'created_at', 'updated_at', 'reference_number')
    list_filter = ('payment_status', 'created_at', 'updated_at')
    search_fields = ('user__username', 'organization__name', 'reference_number')
    readonly_fields = ('reference_number',)


# PAYMENT SUBSCRIPTION Admin ------------------------------------------------------
@admin.register(PaymentSubscription)
class PaymentSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'subscription_pricing', 'amount', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = ('user__username', 'subscription_pricing__pricing_type')
    list_editable = ('is_active',)


# PAYMENT ADVERTISEMENT Admin -----------------------------------------------------
@admin.register(PaymentAdvertisement)
class PaymentAdvertisementAdmin(admin.ModelAdmin):
    list_display = ('user', 'advertisement_pricing', 'amount', 'start_date', 'end_date')
    list_filter = ('start_date', 'end_date')
    search_fields = ('user__username', 'advertisement_pricing__pricing_type')


# PAYMENT DONATION Admin ----------------------------------------------------------
@admin.register(PaymentDonation)
class PaymentDonationAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'created_at', 'message')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'message')


# PAYMENT SHOPPING CART Admin -----------------------------------------------------
@admin.register(PaymentShoppingCart)
class PaymentShoppingCartAdmin(admin.ModelAdmin):
    list_display = ('user', 'shopping_cart', 'amount', 'billing_address', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'shopping_cart__id', 'billing_address__address_line')


# PAYMENT INVOICE Admin -----------------------------------------------------------
@admin.register(PaymentInvoice)
class PaymentInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'payment', 'issued_date', 'due_date', 'is_paid')
    list_filter = ('is_paid', 'issued_date', 'due_date')
    search_fields = ('invoice_number', 'payment__reference_number')
    readonly_fields = ('invoice_number',)

# apps/profiles/admin/customer.py

from django.contrib import admin

from apps.profiles.models.customer import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['user', 'customer_phone_number', 'billing_address', 'get_shipping_addresses', 'register_date', 'is_active']
    list_filter = ['is_active', 'register_date', 'deactivation_reason']
    search_fields = ['user__username', 'customer_phone_number']

    fieldsets = (
        ('Customer Info', {'fields': ('user', 'customer_phone_number', 'billing_address', 'shipping_addresses')}),
        ('Status', {'fields': ('is_active', 'deactivation_reason', 'deactivation_note')}),
        ('Dates', {'fields': ('register_date',)}),
    )

    autocomplete_fields = ['billing_address', 'shipping_addresses']

    def get_shipping_addresses(self, obj):
        return ", ".join([str(address) for address in obj.shipping_addresses.all()])
    get_shipping_addresses.short_description = 'Shipping Addresses'
# apps/accounts/admin/address_admin.py

from django.contrib import admin
from ..models import Address


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = [
        "street_number",
        "route",
        "locality",
        "administrative_area_level_1",
        "postal_code",
        "country",
        "address_type",
    ]

    search_fields = [
        "street_number",
        "route",
        "locality",
        "administrative_area_level_1",
        "postal_code",
        "country",
    ]

    list_filter = [
        "country",
        "locality",
        "administrative_area_level_1",
    ]

    readonly_fields = ["additional"]
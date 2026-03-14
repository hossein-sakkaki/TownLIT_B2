# apps/accounts/admin/device_admin.py

from django.contrib import admin
from ..models import UserDeviceKey


@admin.register(UserDeviceKey)
class UserDeviceKeyAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "device_name",
        "device_id",
        "ip_address",
        "location_city",
        "location_region",
        "location_country",
        "timezone",
        "organization",
        "postal_code",
        "latitude",
        "longitude",
        "last_used",
        "is_active",
    )

    list_filter = (
        "is_active",
        "location_country",
        "location_region",
        "organization",
        "timezone",
    )

    search_fields = (
        "user__email",
        "device_id",
        "device_name",
        "ip_address",
        "location_city",
        "location_region",
        "location_country",
        "organization",
        "postal_code",
    )

    readonly_fields = (
        "created_at",
        "last_used",
        "ip_address",
        "location_city",
        "location_region",
        "location_country",
        "timezone",
        "organization",
        "postal_code",
        "latitude",
        "longitude",
    )

    ordering = ("-last_used",)
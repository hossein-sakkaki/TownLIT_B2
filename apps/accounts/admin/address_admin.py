# apps/accounts/admin/address_admin.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki (original creation date not recorded in source).
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Mask private delivery instructions in admin; reveal for superusers only."""

import logging

from django.contrib import admin

from ..models import Address


logger = logging.getLogger("townlit.security.data_protection")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = [
        "street_number", "route", "locality", "administrative_area_level_1",
        "postal_code", "country", "address_type",
    ]
    search_fields = [
        "street_number", "route", "locality", "administrative_area_level_1",
        "postal_code", "country",
    ]
    list_filter = ["country", "locality", "administrative_area_level_1"]
    exclude = ("additional", "additional_encrypted")

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return ("additional_revealed",)
        return ("additional_masked",)

    @admin.display(description="Additional (restricted)")
    def additional_masked(self, obj):
        if obj is None:
            return "—"
        if getattr(obj, "additional_encrypted", None) is not None:
            return "Protected — superuser access required"
        if getattr(obj, "additional", None) is not None:
            return "Protected — superuser access required"
        return "—"

    @admin.display(description="Additional")
    def additional_revealed(self, obj):
        if obj is None:
            return "—"
        value = obj.additional_for_read()
        return "—" if value is None else value

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if request.method == "GET" and request.user.is_superuser:
            logger.info(
                "address_additional_admin_view actor_id=%s address_id=%s",
                request.user.pk, object_id,
            )
        return super().change_view(request, object_id, form_url, extra_context)

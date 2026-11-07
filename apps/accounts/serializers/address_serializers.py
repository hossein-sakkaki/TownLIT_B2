# apps/accounts/serializers/address_serializers.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki (original creation date not recorded in source).
# Last Update by Hossein Sakkaki on 2026-11-06.
#

from rest_framework import serializers

from ..models import Address


class AddressSerializer(serializers.ModelSerializer):
    additional = serializers.CharField(max_length=400, allow_blank=True, allow_null=True, required=False)

    class Meta:
        model = Address
        fields = (
            "id", "street_number", "route", "locality",
            "administrative_area_level_1", "postal_code", "country",
            "additional", "address_type",
        )

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result["additional"] = instance.additional_for_read()
        return result

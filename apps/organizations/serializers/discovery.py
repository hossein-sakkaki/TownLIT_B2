# apps/organizations/serializers/discovery.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-02.
# Last Update by Hossein Sakkaki on 2026-10-20.
#

from rest_framework import serializers
from rest_framework.fields import empty

from apps.organizations.constants import (
    OrganizationKind,
    OrganizationServiceDeliveryMode,
)
from apps.organizations.models import Organization
from apps.organizations.selectors.verification import (
    is_organization_verified,
)


def _file_url(field, *, request=None) -> str | None:
    if not field:
        return None

    try:
        url = field.url
    except Exception:
        return None

    return (
        request.build_absolute_uri(url)
        if request
        else url
    )


class OptionalQueryBooleanField(serializers.BooleanField):
    """Keep omitted query booleans distinct from explicit false values.

    DRF can interpret a missing field in a QueryDict as unchecked HTML input.
    For an optional search filter, omission must mean no filtering.
    """

    def get_value(self, dictionary):
        if self.field_name not in dictionary:
            return empty
        return super().get_value(dictionary)


class OrganizationDiscoveryQuerySerializer(
    serializers.Serializer
):
    q = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
        max_length=160,
    )

    kind = serializers.ChoiceField(
        choices=OrganizationKind.choices,
        required=False,
        allow_null=True,
    )

    country = serializers.CharField(
        required=False,
        allow_blank=False,
        allow_null=True,
        trim_whitespace=True,
        max_length=2,
    )

    city = serializers.CharField(
        required=False,
        allow_blank=False,
        allow_null=True,
        trim_whitespace=True,
        max_length=120,
    )

    service_delivery_mode = serializers.ChoiceField(
        choices=OrganizationServiceDeliveryMode.choices,
        required=False,
        allow_null=True,
    )

    verified = OptionalQueryBooleanField(
        required=False,
        allow_null=True,
    )

    def validate_country(self, value):
        if value is None:
            return None
        return str(value).strip().upper()


class OrganizationDiscoveryResultSerializer(
    serializers.ModelSerializer
):
    logo_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "public_id",
            "name",
            "short_name",
            "tagline",
            "slug",
            "kind",
            "activity_areas",
            "country",
            "province_region",
            "city",
            "logo_url",
            "thumbnail_url",
            "brand_color",
            "service_delivery_mode",
            "is_verified",
        ]
        read_only_fields = fields

    def get_logo_url(self, obj):
        return _file_url(
            obj.logo,
            request=self.context.get("request"),
        )

    def get_thumbnail_url(self, obj):
        return _file_url(
            obj.thumbnail,
            request=self.context.get("request"),
        )

    def get_is_verified(self, obj):
        precomputed = getattr(
            obj,
            "_discovery_is_verified",
            None,
        )

        if precomputed is not None:
            return bool(precomputed)

        return is_organization_verified(
            organization=obj
        )


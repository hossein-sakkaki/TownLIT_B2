# apps/profiles/serializers/organization.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-13.
# Last Update by Hossein Sakkaki on 2026-09-13.
#

from rest_framework import serializers

from apps.organizations.models import Organization


class ProfileOrganizationSerializer(
    serializers.ModelSerializer
):
    org_name = serializers.CharField(
        source="name",
        read_only=True,
    )

    class Meta:
        model = Organization
        fields = (
            "id",
            "org_name",
            "slug",
        )
        read_only_fields = fields
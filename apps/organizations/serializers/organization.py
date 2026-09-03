# apps/organizations/serializers/organization.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from rest_framework import serializers

from apps.organizations.constants import OrganizationKind
from apps.organizations.models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    follower_count = serializers.IntegerField(
        read_only=True,
        default=0,
    )
    member_count = serializers.IntegerField(
        read_only=True,
        default=0,
    )
    viewer_relationship = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "public_id",
            "name",
            "slug",
            "kind",
            "description",
            "history",
            "statement_of_faith",
            "statement_of_purpose",
            "public_email",
            "public_phone_number",
            "website_url",
            "country",
            "city",
            "primary_language",
            "secondary_language",
            "timezone",
            "logo_url",
            "status",
            "visibility",
            "follower_count",
            "member_count",
            "viewer_relationship",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_viewer_relationship(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or not getattr(user, "is_authenticated", False):
            return None

        connection = (
            obj.connections
            .filter(
                user=user,
                status="active",
            )
            .only("relationship_type")
            .first()
        )

        return (
            connection.relationship_type
            if connection
            else None
        )

    def get_logo_url(self, obj):
        if not obj.logo:
            return None

        request = self.context.get("request")

        try:
            url = obj.logo.url
        except Exception:
            return None

        return (
            request.build_absolute_uri(url)
            if request
            else url
        )


class OrganizationWriteSerializer(serializers.ModelSerializer):
    kind = serializers.ChoiceField(
        choices=OrganizationKind.choices,
    )

    class Meta:
        model = Organization
        fields = [
            "name",
            "kind",
            "description",
            "history",
            "statement_of_faith",
            "statement_of_purpose",
            "public_email",
            "public_phone_number",
            "website_url",
            "country",
            "city",
            "primary_language",
            "secondary_language",
            "timezone",
            "logo",
            "visibility",
        ]
        extra_kwargs = {
            "name": {"required": True},
            "kind": {"required": True},
        }

    def validate_name(self, value):
        normalized = " ".join(str(value or "").split())

        if not normalized:
            raise serializers.ValidationError(
                "Organization name is required."
            )

        return normalized

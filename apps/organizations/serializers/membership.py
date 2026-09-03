# apps/organizations/serializers/membership.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.organizations.models import (
    OrganizationMembership,
    OrganizationMembershipRequest,
)


class OrganizationMembershipRequestSerializer(serializers.ModelSerializer):
    member_user = UserMiniSerializer(
        source="member.user",
        read_only=True,
    )

    class Meta:
        model = OrganizationMembershipRequest
        fields = [
            "public_id",
            "organization_id",
            "member_id",
            "member_user",
            "direction",
            "status",
            "message",
            "response_message",
            "expires_at",
            "responded_at",
            "created_at",
        ]
        read_only_fields = fields


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    member_user = UserMiniSerializer(
        source="member.user",
        read_only=True,
    )

    class Meta:
        model = OrganizationMembership
        fields = [
            "public_id",
            "organization_id",
            "member_id",
            "member_user",
            "status",
            "joined_at",
            "suspended_at",
            "ended_at",
            "created_at",
        ]
        read_only_fields = fields

# apps/conversation/serializers/organization/direct.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.conversation.models import OrganizationDialogueContext
from apps.conversation.serializers.message import MessageSerializer
from apps.conversation.services.organization.direct_selectors import (
    organization_direct_unread_count,
)
from apps.conversation.services.organization.direct_workflow import (
    membership_is_assignable_to_messenger,
)

from .context import organization_identity_payload


def organization_assignment_payload(membership, *, request=None):
    if membership is None:
        return None

    return {
        "membership_public_id": str(membership.public_id),
        "user": SimpleCustomUserSerializer(
            membership.member.user,
            context={"request": request} if request else {},
        ).data,
    }


class OrganizationDirectThreadSerializer(serializers.ModelSerializer):
    public_id = serializers.UUIDField(read_only=True)
    dialogue_slug = serializers.CharField(source="dialogue.slug", read_only=True)
    organization = serializers.SerializerMethodField()
    participant = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    has_unread = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationDialogueContext
        fields = [
            "public_id",
            "dialogue_slug",
            "organization",
            "participant",
            "status",
            "waiting_for",
            "assigned_to",
            "unread_count",
            "has_unread",
            "last_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_organization(self, obj):
        return organization_identity_payload(
            obj.organization,
            request=self.context.get("request"),
        )

    def get_participant(self, obj):
        return SimpleCustomUserSerializer(
            obj.participant_user,
            context=self.context,
        ).data

    def get_assigned_to(self, obj):
        membership = obj.assigned_to_membership
        if membership is None:
            return None

        annotated = getattr(obj, "has_effective_assignee", None)
        if annotated is False:
            return None
        if annotated is None and not membership_is_assignable_to_messenger(
            membership
        ):
            return None

        return organization_assignment_payload(
            membership,
            request=self.context.get("request"),
        )

    def get_unread_count(self, obj):
        annotated = getattr(obj, "operator_unread_count", None)
        if annotated is not None:
            return int(annotated)

        request = self.context.get("request")
        if not request or not getattr(request, "user", None):
            return 0
        return organization_direct_unread_count(
            context=obj,
            operator_user=request.user,
        )

    def get_has_unread(self, obj):
        annotated = getattr(obj, "has_unread", None)
        if annotated is not None:
            return bool(annotated)
        return self.get_unread_count(obj) > 0

    def get_last_message(self, obj):
        request = self.context.get("request")
        if not request:
            return None

        message = obj.dialogue.last_message
        if not message or not message.is_delivery_ready:
            return None
        return MessageSerializer(
            message,
            context={
                "request": request,
                "organization_operator_view": True,
            },
        ).data

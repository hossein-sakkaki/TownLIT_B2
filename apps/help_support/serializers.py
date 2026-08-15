# apps/help_support/serializers.py

from django.conf import settings
from rest_framework import serializers

from apps.help_support.constants import (
    SUPPORT_CATEGORY_CHOICES,
    SUPPORT_AREA_CHOICES,
    SUPPORT_SOURCE_CHOICES,
    SUPPORT_SOURCE_SETTINGS,
)
from apps.help_support.models import (
    SupportTicket,
    SupportTicketMessage,
)
from apps.help_support.services.tickets import SupportTicketService


class SupportTicketMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicketMessage
        fields = [
            "id",
            "sender_type",
            "body",
            "created_at",
        ]
        read_only_fields = fields


class SupportTicketSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            "public_id",
            "category",
            "area",
            "source",
            "subject",
            "status",
            "priority",
            "reply_email",
            "context_type",
            "context_id",
            "client_app_version",
            "client_platform",
            "last_message_at",
            "resolved_at",
            "closed_at",
            "created_at",
            "updated_at",
            "messages",
        ]
        read_only_fields = fields

    def get_messages(self, obj):
        messages = obj.messages.filter(is_internal=False).order_by("created_at", "id")

        return SupportTicketMessageSerializer(
            messages,
            many=True,
            context=self.context,
        ).data


class SupportTicketCreateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(
        choices=SUPPORT_CATEGORY_CHOICES,
    )

    area = serializers.ChoiceField(
        choices=SUPPORT_AREA_CHOICES,
    )

    source = serializers.ChoiceField(
        choices=SUPPORT_SOURCE_CHOICES,
        required=False,
        default=SUPPORT_SOURCE_SETTINGS,
    )

    subject = serializers.CharField(
        max_length=160,
        trim_whitespace=True,
    )

    message = serializers.CharField(
        max_length=8000,
        trim_whitespace=True,
    )

    reply_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        max_length=254,
    )

    context_type = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=64,
    )

    context_id = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
    )

    client_app_version = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=40,
    )

    client_platform = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=32,
    )

    def validate_subject(self, value):
        cleaned = value.strip()

        if len(cleaned) < 3:
            raise serializers.ValidationError(
                "Please provide a short subject."
            )

        return cleaned

    def validate_message(self, value):
        cleaned = value.strip()

        if len(cleaned) < 10:
            raise serializers.ValidationError(
                "Please provide a little more detail so TownLIT can help."
            )

        return cleaned

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        reply_email = (
            validated_data.get("reply_email")
            or getattr(user, "email", "")
            or ""
        )

        return SupportTicketService.create_ticket(
            requester=user,
            reply_email=reply_email,
            category=validated_data["category"],
            area=validated_data["area"],
            source=validated_data.get("source") or SUPPORT_SOURCE_SETTINGS,
            subject=validated_data["subject"],
            message=validated_data["message"],
            context_type=validated_data.get("context_type") or "",
            context_id=validated_data.get("context_id") or "",
            client_app_version=validated_data.get("client_app_version") or "",
            client_platform=validated_data.get("client_platform") or "",
        )


class SupportTicketReplySerializer(serializers.Serializer):
    message = serializers.CharField(
        max_length=8000,
        trim_whitespace=True,
    )

    def validate_message(self, value):
        cleaned = value.strip()

        if not cleaned:
            raise serializers.ValidationError(
                "Message cannot be empty."
            )

        return cleaned


class SupportBootstrapSerializer(serializers.Serializer):
    support_email = serializers.EmailField()
    categories = serializers.ListField()
    areas = serializers.ListField()
    max_subject_length = serializers.IntegerField()
    max_message_length = serializers.IntegerField()
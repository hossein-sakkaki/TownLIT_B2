# apps/conversation/serializers/pins.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.conversation.models import DialoguePin, MessagePin

from .dialogue import DialogueSerializer
from .message import MessageSerializer


class DialoguePinSerializer(serializers.ModelSerializer):
    dialogue = serializers.SerializerMethodField()

    class Meta:
        model = DialoguePin
        fields = ["id", "position", "pinned_at", "dialogue"]

    def get_dialogue(self, obj):
        serializer = DialogueSerializer(
            obj.dialogue,
            context=self.context,
        )
        return serializer.data


class MessagePinSerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()
    pinned_by = SimpleCustomUserSerializer(read_only=True)

    class Meta:
        model = MessagePin
        fields = [
            "id",
            "position",
            "pin_duration",
            "expires_at",
            "reminders_enabled",
            "next_reminder_at",
            "last_reminded_at",
            "created_at",
            "pinned_by",
            "message",
        ]

    def get_message(self, obj):
        request = self.context.get("request")
        device_id = (
            self.context.get("device_id")
            or (request.query_params.get("device_id") if request else None)
            or (request.headers.get("X-Device-ID") if request else None)
        )
        serializer = MessageSerializer(
            obj.message,
            context={"request": request, "device_id": device_id},
        )
        return serializer.data

# apps/conversation/views/mixins/dialogue_pins.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conversation.models import Dialogue
from apps.conversation.serializers import DialoguePinSerializer, MessagePinSerializer
from apps.conversation.services.dialogue_pins import (
    list_pinned_dialogues_for_user,
    pin_dialogue_for_user,
    unpin_dialogue_for_user,
)
from apps.conversation.services.event_contracts import (
    build_dialogue_pinned_event_data,
    build_dialogue_unpinned_event_data,
)
from apps.conversation.services.message_pins import list_pinned_messages_for_dialogue
from apps.conversation.services.realtime_dispatch import conv_group_send
from apps.core.security.decorators import require_litshield_access


class DialoguePinActionsMixin:
    @action(detail=True, methods=["post"], url_path="pin-dialogue", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def pin_dialogue(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, participants=request.user)
        result = pin_dialogue_for_user(
            dialogue=dialogue,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )
        device_id = (
            request.data.get("device_id")
            or request.query_params.get("device_id")
            or request.headers.get("X-Device-ID", "")
        )
        serialized_dialogue = self._serialize_single_dialogue(
            request=request,
            dialogue=dialogue,
            device_id=device_id,
        )
        # Push realtime update only to the acting user's sessions
        conv_group_send(
            f"user_{request.user.id}",
            "dialogue_pinned",
            build_dialogue_pinned_event_data(dialogue=serialized_dialogue),
        )
        return Response(
            {
                "message": result["payload"]["message"],
                "dialogue": serialized_dialogue,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="unpin-dialogue", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def unpin_dialogue(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, participants=request.user)
        result = unpin_dialogue_for_user(
            dialogue=dialogue,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )
        device_id = (
            request.data.get("device_id")
            or request.query_params.get("device_id")
            or request.headers.get("X-Device-ID", "")
        )
        serialized_dialogue = self._serialize_single_dialogue(
            request=request,
            dialogue=dialogue,
            device_id=device_id,
        )
        # Push realtime update only to the acting user's sessions
        conv_group_send(
            f"user_{request.user.id}",
            "dialogue_unpinned",
            build_dialogue_unpinned_event_data(dialogue=serialized_dialogue),
        )
        return Response(
            {
                "message": result["payload"]["message"],
                "dialogue": serialized_dialogue,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="pinned-dialogues", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def pinned_dialogues(self, request):
        result = list_pinned_dialogues_for_user(
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )
        pins = result["payload"]["pins"]
        serializer = DialoguePinSerializer(
            pins,
            many=True,
            context={"request": request},
        )
        return Response(
            {
                "count": result["payload"]["count"],
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="pinned-messages", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def pinned_messages(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, participants=request.user)
        result = list_pinned_messages_for_dialogue(
            dialogue=dialogue,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )
        device_id = (
            request.query_params.get("device_id", "")
            or request.headers.get("X-Device-ID", "")
        ).strip().lower()
        serializer = MessagePinSerializer(
            result["payload"]["pins"],
            many=True,
            context={"request": request, "device_id": device_id},
        )
        return Response(
            {
                "count": result["payload"]["count"],
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

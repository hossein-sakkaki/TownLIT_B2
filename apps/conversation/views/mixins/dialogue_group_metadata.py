# apps/conversation/views/mixins/dialogue_group_metadata.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conversation.models import DialogueParticipant
from apps.conversation.policies import (
    ConversationMutationAction,
    ConversationMutationPolicy,
)
from apps.conversation.serializers import CreateGroupSerializer, DialogueSerializer, UpdateGroupInfoSerializer
from apps.conversation.services.content_safety import enforce_group_metadata_content_safety
from apps.conversation.services.dialogue_lifecycle import create_group_dialogue
from apps.conversation.services.media_content_safety import enforce_group_image_content_safety
from apps.core.security.decorators import require_litshield_access

from ..helpers import _broadcast_group_updated


class DialogueGroupMetadataActionsMixin:
    @staticmethod
    def _mutation_denied_response(dialogue, action):
        decision = ConversationMutationPolicy.check(
            dialogue=dialogue,
            action=action,
        )
        if decision.allowed:
            return None
        return Response(
            {
                "error": decision.message,
                "code": decision.code,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    @action(detail=False, methods=['post'], url_path='create-group', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def create_group(self, request):
        serializer = CreateGroupSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        group_name = serializer.validated_data["group_name"]
        enforce_group_metadata_content_safety(
            text=group_name,
            actor=request.user,
            field_name="group_name",
        )
        group_image = serializer.validated_data.get(
            "group_image"
        )
        if group_image:
            enforce_group_image_content_safety(
                file_obj=group_image,
                actor=request.user,
                field_name="group_image",
                validation_field_name="group_image",
                mime_type=getattr(
                    group_image,
                    "content_type",
                    None,
                ),
            )
        result = create_group_dialogue(
            acting_user=request.user,
            group_name=group_name,
            group_image=group_image,
        )
        if not result.get("ok"):
            return Response(
                {
                    "error": result["message"],
                    "code": result["code"],
                },
                status=result["status"],
            )
        dialogue = result["payload"]["dialogue"]
        output_serializer = DialogueSerializer(
            dialogue,
            context={"request": request},
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="update-group-image", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def update_group_image(self, request, **kwargs):
        dialogue = self.get_object()
        if not dialogue.is_group:
            return Response(
                {"detail": "Only group dialogues can have images."},
                status=status.HTTP_400_BAD_REQUEST
            )
        denied = self._mutation_denied_response(
            dialogue,
            ConversationMutationAction.UPDATE_GROUP_IMAGE,
        )
        if denied:
            return denied
        participant = DialogueParticipant.objects.filter(
            dialogue=dialogue,
            user=request.user
        ).first()
        if not participant:
            return Response(
                {"detail": "You are not a participant of this group."},
                status=status.HTTP_404_NOT_FOUND
            )
        if participant.role not in ["founder", "elder"]:
            return Response(
                {"detail": "You don't have permission to update the group image."},
                status=status.HTTP_403_FORBIDDEN
            )
        group_image = request.FILES.get("group_image")
        if not group_image:
            return Response(
                {
                    "detail": (
                        "No image uploaded."
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )
        enforce_group_image_content_safety(
            file_obj=group_image,
            actor=request.user,
            field_name="group_image",
            validation_field_name="group_image",
            mime_type=getattr(
                group_image,
                "content_type",
                None,
            ),
        )
        dialogue.group_image = group_image
        dialogue.group_avatar_version = (dialogue.group_avatar_version or 0) + 1
        dialogue.save(update_fields=["group_image", "group_avatar_version"])
        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="group_image_updated",
            actor_user=request.user,
        )
        serializer = DialogueSerializer(dialogue, context={"request": request})
        return Response(
            {
                "detail": "Group image updated successfully.",
                "dialogue": serializer.data,
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post", "patch"], url_path="update-group-info", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def update_group_info(self, request, **kwargs):
        dialogue = self.get_object()
        if not getattr(dialogue, "is_group", False):
            return Response({"detail": "Only group dialogues can be updated."}, status=status.HTTP_400_BAD_REQUEST)
        denied = self._mutation_denied_response(
            dialogue,
            ConversationMutationAction.UPDATE_GROUP_INFO,
        )
        if denied:
            return denied
        try:
            participant = DialogueParticipant.objects.get(dialogue=dialogue, user=request.user)
            if participant.role not in ["founder", "elder"]:
                return Response({"detail": "You don't have permission to update group info."}, status=status.HTTP_403_FORBIDDEN)
        except DialogueParticipant.DoesNotExist:
            return Response({"detail": "You are not a participant of this group."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UpdateGroupInfoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        if "group_name" in payload:
            incoming_group_name = (
                payload.get(
                    "group_name"
                )
                or ""
            ).strip()
            if (
                incoming_group_name
                and incoming_group_name
                != dialogue.group_name
            ):
                enforce_group_metadata_content_safety(
                    text=incoming_group_name,
                    actor=request.user,
                    field_name="group_name",
                )
        field_map = {
            "group_name": "group_name",
        }
        updated_fields = {}
        unsupported_keys = []
        with transaction.atomic():
            for client_key, value in payload.items():
                model_field = field_map.get(client_key)
                if not model_field:
                    unsupported_keys.append(client_key)
                    continue
                if not hasattr(dialogue, model_field):
                    unsupported_keys.append(client_key)
                    continue
                # Skip no-op updates
                current_val = getattr(dialogue, model_field, None)
                if isinstance(value, str):
                    value = value.strip()
                if value == current_val:
                    continue
                setattr(dialogue, model_field, value)
                updated_fields[model_field] = value
            if not updated_fields:
                if unsupported_keys:
                    return Response(
                        {"detail": "No supported fields provided.", "unsupported": unsupported_keys},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                return Response({"detail": "No changes detected."}, status=status.HTTP_200_OK)
            try:
                dialogue.save(update_fields=list(updated_fields.keys()))
            except Exception:
                dialogue.save()
        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="group_info_updated",
            actor_user=request.user,
        )
        return Response(
            {
                "detail": "Group info updated successfully.",
                "updated": updated_fields,
                "unsupported": unsupported_keys or [],
            },
            status=status.HTTP_200_OK,
        )

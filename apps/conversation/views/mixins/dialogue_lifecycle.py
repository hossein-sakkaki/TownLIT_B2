# apps/conversation/views/mixins/dialogue_lifecycle.py
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
from apps.conversation.services.dialogue_lifecycle import smart_delete_dialogue_for_user
from apps.core.security.decorators import require_litshield_access


class DialogueLifecycleActionsMixin:
    @action(detail=True, methods=['post'], url_path='smart-delete', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def smart_delete_dialogue(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, participants=request.user)
        result = smart_delete_dialogue_for_user(
            dialogue=dialogue,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )
        payload = result["payload"]
        return Response(
            {'message': payload["message"]},
            status=status.HTTP_200_OK
        )

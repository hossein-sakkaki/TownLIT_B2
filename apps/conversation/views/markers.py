# apps/conversation/views/markers.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conversation.models import Dialogue, UserDialogueMarker
from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationContextPolicy,
)
from apps.conversation.permissions import ConversationAccessPermission
from apps.conversation.serializers import UserDialogueMarkerSerializer
from apps.core.security.decorators import require_litshield_access


class UserDialogueMarkerViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def list(self, request):
        markers = list(
            UserDialogueMarker.objects
            .filter(user=request.user)
            .select_related("dialogue__organization_context__organization")
        )
        markers = [
            marker
            for marker in markers
            if (
                not ConversationContextPolicy.resolve(marker.dialogue).is_organization
                or ConversationAccessPolicy.can_view(
                    dialogue=marker.dialogue,
                    user=request.user,
                ).allowed
            )
        ]
        serializer = UserDialogueMarkerSerializer(markers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='mark-dialogue', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def mark_dialogue(self, request):
        dialogue_slug = request.data.get('dialogue_slug')
        is_sensitive = request.data.get('is_sensitive', False)
        delete_policy = request.data.get('delete_policy', 'SOFT_DELETE')
        if not dialogue_slug:
            return Response({'detail': 'Dialogue slug is required.'}, status=status.HTTP_400_BAD_REQUEST)
        dialogue = get_object_or_404(Dialogue, slug=dialogue_slug, participants=request.user)
        if ConversationContextPolicy.resolve(dialogue).is_organization:
            access = ConversationAccessPolicy.can_view(
                dialogue=dialogue,
                user=request.user,
            )
            if not access.allowed:
                return Response(
                    {"error": access.message, "code": access.code},
                    status=status.HTTP_403_FORBIDDEN,
                )
        marker, created = UserDialogueMarker.objects.get_or_create(
            user=request.user,
            dialogue=dialogue,
            defaults={'is_sensitive': is_sensitive, 'delete_policy': delete_policy}
        )
        if not created:
            marker.is_sensitive = is_sensitive
            marker.delete_policy = delete_policy
            marker.save()
        serializer = UserDialogueMarkerSerializer(marker)
        return Response(serializer.data, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='unmark-dialogue', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def unmark_dialogue(self, request, pk=None):
        marker = get_object_or_404(UserDialogueMarker, pk=pk, user=request.user)
        marker.delete()
        return Response({'detail': 'Dialogue unmarked as sensitive.'}, status=status.HTTP_204_NO_CONTENT)

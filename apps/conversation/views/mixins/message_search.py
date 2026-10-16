# apps/conversation/views/mixins/message_search.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conversation.models import Dialogue, MessageSearchIndex
from apps.conversation.policies import ConversationAccessPolicy
from apps.conversation.serializers import MessageSerializer


class MessageSearchActionsMixin:
    @action(detail=True, methods=["get"], url_path="search-messages", permission_classes=[IsAuthenticated])
    def search_messages(self, request, pk=None):
        query = request.query_params.get("q")
        if not query:
            return Response({"error": "Search query `q` is required."}, status=400)
        dialogue = get_object_or_404(Dialogue, slug=pk)
        access = ConversationAccessPolicy.can_view(
            dialogue=dialogue,
            user=request.user,
        )
        if not access.allowed:
            return Response(
                {"error": access.message, "code": access.code},
                status=403,
            )
        if dialogue.is_group:
            matching_message_ids = (
                MessageSearchIndex.objects
                .filter(plaintext__icontains=query, message__dialogue=dialogue)
                .values_list("message_id", flat=True)
            )
            messages = (
                dialogue.visible_non_system_messages_for_user(
                    request.user
                )
                .filter(id__in=matching_message_ids)
                .order_by("-timestamp")[:100]
            )
            serializer = MessageSerializer(messages, many=True, context={"request": request})
            return Response(serializer.data)
        else:
            return Response({
                "note": "Client-side search is required for encrypted private chats.",
                "messages": []
            })

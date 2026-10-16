# apps/conversation/views/message.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conversation.models import Message
from apps.conversation.policies import (
    ConversationContextKind,
    ConversationContextPolicy,
)
from apps.conversation.permissions import ConversationAccessPermission, IsDialogueParticipant
from apps.conversation.serializers import MessageSerializer

from .mixins.message_core import MessageCoreActionsMixin
from .mixins.message_forward import MessageForwardActionsMixin
from .mixins.message_media import MessageMediaActionsMixin
from .mixins.message_pins import MessagePinActionsMixin
from .mixins.message_reactions import MessageReactionActionsMixin
from .mixins.message_search import MessageSearchActionsMixin
from .mixins.message_state import MessageStateActionsMixin


class MessageViewSet(
    MessageCoreActionsMixin,
    MessageMediaActionsMixin,
    MessageStateActionsMixin,
    MessageSearchActionsMixin,
    MessagePinActionsMixin,
    MessageForwardActionsMixin,
    MessageReactionActionsMixin,
    viewsets.ModelViewSet,
):
    permission_classes = [
        IsAuthenticated,
        ConversationAccessPermission,
        IsDialogueParticipant,
    ]
    queryset = Message.objects.all()
    serializer_class = MessageSerializer

    @staticmethod
    def _is_managed_community(message):
        return (
            ConversationContextPolicy.resolve(message.dialogue).kind
            == ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY
        )

    def update(self, request, *args, **kwargs):
        message = self.get_object()
        if self._is_managed_community(message):
            return Response(
                {
                    "error": (
                        "Use the Conversation message actions for "
                        "Members Community messages."
                    ),
                    "code": "organization_community_managed_message",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        message = self.get_object()
        if self._is_managed_community(message):
            return Response(
                {
                    "error": (
                        "Use the Conversation delete actions for "
                        "Members Community messages."
                    ),
                    "code": "organization_community_managed_message",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

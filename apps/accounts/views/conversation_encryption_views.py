#
#  apps/accounts/views/conversation_encryption_views.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-07-28.
#  Last Update by Hossein Sakkaki on 2026-07-28.
#


from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.throttling import (
    ScopedRateThrottle,
)

from apps.accounts.serializers.conversation_encryption_serializers import (
    ConversationEncryptionStateSerializer,
)
from apps.accounts.services.conversation_encryption_state import (
    resolve_conversation_encryption_state,
)


class ConversationEncryptionViewSet(
    viewsets.ViewSet
):
    permission_classes = [
        IsAuthenticated,
    ]

    throttle_classes = [
        ScopedRateThrottle,
    ]

    throttle_scope = "crypto"

    @action(
        detail=False,
        methods=[
            "get",
        ],
        url_path="state",
    )
    def state(
        self,
        request,
    ):
        """
        Return the authoritative encryption identity state.
        """

        resolved_state = (
            resolve_conversation_encryption_state(
                user=request.user,
            )
        )

        serializer = (
            ConversationEncryptionStateSerializer(
                data=resolved_state.as_dict(),
            )
        )

        serializer.is_valid(
            raise_exception=True,
        )

        return Response(
            serializer.validated_data,
            status=status.HTTP_200_OK,
        )
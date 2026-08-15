# apps/help_support/views.py

from django.conf import settings

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.help_support.constants import (
    SUPPORT_CATEGORY_CHOICES,
    SUPPORT_AREA_CHOICES,
)
from apps.help_support.models import SupportTicket
from apps.help_support.serializers import (
    SupportTicketSerializer,
    SupportTicketCreateSerializer,
    SupportTicketReplySerializer,
)
from apps.help_support.services.tickets import SupportTicketService


class SupportBootstrapViewSet(viewsets.ViewSet):
    """
    Public Help & Support bootstrap.

    Contact information is intentionally public so TownLIT publishes
    a direct support route even before authentication.

    Ticket creation and ticket history remain authenticated.
    """

    permission_classes = [AllowAny]
    http_method_names = ["get", "head", "options"]

    def list(self, request):
        support_email = getattr(
            settings,
            "TOWNLIT_SUPPORT_EMAIL",
            "support@townlit.com",
        )

        return Response(
            {
                "support_email": support_email,
                "categories": [
                    {
                        "value": value,
                        "label": label,
                    }
                    for value, label in SUPPORT_CATEGORY_CHOICES
                ],
                "areas": [
                    {
                        "value": value,
                        "label": label,
                    }
                    for value, label in SUPPORT_AREA_CHOICES
                ],
                "max_subject_length": 160,
                "max_message_length": 8000,
            },
            status=status.HTTP_200_OK,
        )


class SupportTicketViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    User-owned Help & Support tickets.

    Important:
    - A user can only read/reply to their own tickets.
    - Staff/internal messages are filtered by the output serializer.
    - Existing API paths and response envelopes are preserved.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = SupportTicketSerializer
    lookup_field = "public_id"

    http_method_names = [
        "get",
        "post",
        "head",
        "options",
    ]

    def get_queryset(self):
        return (
            SupportTicket.objects
            .filter(requester=self.request.user)
            .select_related(
                "requester",
                "assigned_to",
            )
            .prefetch_related("messages")
            .order_by(
                "-last_message_at",
                "-created_at",
            )
        )

    def get_serializer_class(self):
        if self.action == "create":
            return SupportTicketCreateSerializer

        if self.action == "reply":
            return SupportTicketReplySerializer

        return SupportTicketSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)

        ticket = serializer.save()

        output = SupportTicketSerializer(
            ticket,
            context=self.get_serializer_context(),
        )

        return Response(
            {
                "message": "Your request has been sent to TownLIT Support.",
                "data": output.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="reply",
    )
    def reply(self, request, public_id=None):
        ticket = self.get_object()

        serializer = self.get_serializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)

        SupportTicketService.add_user_message(
            ticket=ticket,
            requester=request.user,
            body=serializer.validated_data["message"],
        )

        ticket.refresh_from_db()

        output = SupportTicketSerializer(
            ticket,
            context=self.get_serializer_context(),
        )

        return Response(
            {
                "message": "Your reply has been sent.",
                "data": output.data,
            },
            status=status.HTTP_200_OK,
        )
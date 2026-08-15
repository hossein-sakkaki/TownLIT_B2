# apps/help_support/services/tickets.py

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.help_support.constants import (
    SUPPORT_STATUS_CLOSED,
    SUPPORT_SENDER_USER,
)
from apps.help_support.models import (
    SupportTicket,
    SupportTicketMessage,
)


class SupportTicketService:
    @staticmethod
    @transaction.atomic
    def create_ticket(
        *,
        requester,
        reply_email: str,
        category: str,
        area: str,
        source: str,
        subject: str,
        message: str,
        context_type: str = "",
        context_id: str = "",
        client_app_version: str = "",
        client_platform: str = "",
    ) -> SupportTicket:
        now = timezone.now()

        ticket = SupportTicket.objects.create(
            requester=requester,
            reply_email=(reply_email or "").strip(),
            category=category,
            area=area,
            source=source,
            subject=(subject or "").strip(),
            context_type=(context_type or "").strip(),
            context_id=(context_id or "").strip(),
            client_app_version=(client_app_version or "").strip(),
            client_platform=(client_platform or "").strip(),
            last_message_at=now,
        )

        SupportTicketMessage.objects.create(
            ticket=ticket,
            author=requester,
            sender_type=SUPPORT_SENDER_USER,
            body=(message or "").strip(),
            is_internal=False,
            created_at=now,
        )

        return ticket

    @staticmethod
    @transaction.atomic
    def add_user_message(
        *,
        ticket: SupportTicket,
        requester,
        body: str,
    ) -> SupportTicketMessage:
        if ticket.status == SUPPORT_STATUS_CLOSED:
            raise serializers.ValidationError({
                "error": "This support request is closed.",
                "code": "support_ticket_closed",
            })

        now = timezone.now()

        message = SupportTicketMessage.objects.create(
            ticket=ticket,
            author=requester,
            sender_type=SUPPORT_SENDER_USER,
            body=(body or "").strip(),
            is_internal=False,
            created_at=now,
        )

        ticket.last_message_at = now
        ticket.save(update_fields=[
            "last_message_at",
            "updated_at",
        ])

        return message
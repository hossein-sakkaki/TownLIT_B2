# apps/help_support/admin.py

from django.contrib import admin
from django.utils.html import format_html

from apps.help_support.models import (
    SupportTicket,
    SupportTicketMessage,
)


class SupportTicketMessageInline(admin.TabularInline):
    model = SupportTicketMessage
    extra = 0
    can_delete = False
    fields = [
        "sender_type",
        "author",
        "body",
        "is_internal",
        "created_at",
    ]
    readonly_fields = [
        "sender_type",
        "author",
        "body",
        "is_internal",
        "created_at",
    ]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        "short_public_id",
        "subject",
        "requester",
        "category",
        "area",
        "status",
        "priority",
        "assigned_to",
        "last_message_at",
    ]

    list_filter = [
        "status",
        "priority",
        "category",
        "area",
        "source",
        "ai_status",
        "created_at",
    ]

    search_fields = [
        "public_id",
        "subject",
        "reply_email",
        "requester__username",
        "requester__email",
        "messages__body",
    ]

    readonly_fields = [
        "public_id",
        "requester",
        "reply_email",
        "category",
        "area",
        "source",
        "subject",
        "context_type",
        "context_id",
        "client_app_version",
        "client_platform",
        "last_message_at",
        "created_at",
        "updated_at",
        "resolved_at",
        "closed_at",
    ]

    fields = [
        "public_id",
        "requester",
        "reply_email",
        "category",
        "area",
        "source",
        "subject",
        "status",
        "priority",
        "assigned_to",
        "ai_status",
        "context_type",
        "context_id",
        "client_app_version",
        "client_platform",
        "last_message_at",
        "resolved_at",
        "closed_at",
        "created_at",
        "updated_at",
    ]

    inlines = [
        SupportTicketMessageInline,
    ]

    ordering = [
        "-last_message_at",
    ]

    list_select_related = [
        "requester",
        "assigned_to",
    ]

    def short_public_id(self, obj):
        return str(obj.public_id)[:8]

    short_public_id.short_description = "Ticket"


@admin.register(SupportTicketMessage)
class SupportTicketMessageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "ticket",
        "sender_type",
        "author",
        "is_internal",
        "created_at",
    ]

    list_filter = [
        "sender_type",
        "is_internal",
        "created_at",
    ]

    search_fields = [
        "ticket__public_id",
        "ticket__subject",
        "body",
        "author__username",
        "author__email",
    ]

    readonly_fields = [
        "ticket",
        "author",
        "sender_type",
        "body",
        "is_internal",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
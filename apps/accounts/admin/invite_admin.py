# apps/accounts/admin/invite_admin.py

from django.contrib import admin
from ..models import InviteCode


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):

    list_display = [
        "code",
        "email",
        "is_used",
        "used_by",
        "created_at",
        "used_at",
        "invite_email_sent",
        "invite_email_sent_at",
    ]

    search_fields = [
        "code",
        "email",
    ]

    list_filter = [
        "is_used",
    ]

    list_editable = [
        "invite_email_sent",
    ]
# apps/posts/admin/reaction.py

import csv

from django.contrib import admin, messages
from django.db import models
from django.db.models import Q
from django.forms import Textarea
from django.http import HttpResponse
from django.utils.html import format_html

from apps.posts.admin.common import (
    admin_change_link_for_ct_and_pk,
    admin_change_link_for_instance,
)
from apps.posts.admin.filters import (
    ContentAppFilter,
    ContentModelFilter,
    HasMessageFilter,
    OfficialVideoFilter,
)
from apps.posts.models.reaction import Reaction


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    """
    Fast, searchable, and target-aware admin for reactions.
    """

    list_display = (
        "user_link",
        "reaction_badge",
        "target_link",
        "target_type",
        "message_snippet",
        "timestamp",
    )

    list_display_links = (
        "user_link",
        "reaction_badge",
        "target_link",
    )

    list_filter = (
        "reaction_type",
        ContentAppFilter,
        ContentModelFilter,
        HasMessageFilter,
        OfficialVideoFilter,
        "timestamp",
    )

    search_fields = (
        "name__username",
        "name__email",
        "name__name",
        "name__family",
        "reaction_type",
        "object_id",
    )

    formfield_overrides = {
        models.TextField: {
            "widget": Textarea(
                attrs={
                    "rows": 3,
                    "style": (
                        "font-family: ui-monospace, SFMono-Regular, Menlo, "
                        "Consolas, monospace; line-height: 1.4;"
                    ),
                }
            ),
        },
    }

    autocomplete_fields = ("name",)
    list_select_related = ("name", "content_type")
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"
    list_per_page = 50

    actions = (
        "clear_empty_messages",
        "remove_suspicious_links",
        "export_csv_secure",
    )

    @admin.display(description="User", ordering="name__username")
    def user_link(self, obj):
        user = getattr(obj, "name", None)
        return admin_change_link_for_instance(user)

    @admin.display(description="Reaction", ordering="reaction_type")
    def reaction_badge(self, obj):
        reaction_type = getattr(obj, "reaction_type", "") or "—"

        color = {
            "like": "#C40233",
            "bless": "#F6C860",
            "gratitude": "#3BAA75",
            "amen": "#A23BEC",
            "encouragement": "#0F52BA",
            "empathy": "#48D1CC",
            "faithfire": "#D73F09",
            "support": "#7A5CA2",
        }.get(reaction_type, "#2B2C30")

        return format_html(
            '<span style="display:inline-block;padding:.15rem .4rem;'
            'border-radius:6px;background:rgba(0,0,0,.04);'
            'border:1px solid rgba(0,0,0,.06);color:{};'
            'font-weight:600;">{}</span>',
            color,
            reaction_type,
        )

    @admin.display(description="Target", ordering="content_type")
    def target_link(self, obj):
        return admin_change_link_for_ct_and_pk(
            getattr(obj, "content_type", None),
            getattr(obj, "object_id", None),
        )

    @admin.display(description="Target Type")
    def target_type(self, obj):
        content_type = getattr(obj, "content_type", None)

        if content_type is None:
            return "-"

        return f"{content_type.app_label}.{content_type.model}"

    @admin.display(description="Message")
    def message_snippet(self, obj):
        message = getattr(obj, "message", "") or ""

        if not message:
            return "—"

        return f"{message[:60]}…" if len(message) > 60 else message

    @admin.action(description="Clear empty/whitespace messages")
    def clear_empty_messages(self, request, queryset):
        updated = queryset.filter(
            Q(message__isnull=True)
            | Q(message="")
            | Q(message__regex=r"^\s+$")
        ).update(message="")

        self.message_user(
            request,
            f"Cleared {updated} message(s).",
            level=messages.SUCCESS,
        )

    @admin.action(description="Remove messages that contain links (anti-spam)")
    def remove_suspicious_links(self, request, queryset):
        suspicious_reactions = queryset.filter(
            Q(message__icontains="http://")
            | Q(message__icontains="https://")
            | Q(message__iregex=r"\bwww\.")
        )

        updated = suspicious_reactions.update(message="")

        self.message_user(
            request,
            f"Removed links from {updated} reaction(s).",
            level=messages.SUCCESS,
        )

    @admin.action(description="Export selected as CSV (decrypted)")
    def export_csv_secure(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Only superusers can export decrypted CSV.",
                level=messages.ERROR,
            )
            return None

        response = HttpResponse(
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = (
            'attachment; filename="reactions.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "user",
                "reaction_type",
                "message",
                "content_type",
                "object_id",
                "timestamp",
            ]
        )

        reactions = queryset.select_related(
            "name",
            "content_type",
        )

        for reaction in reactions.iterator():
            content_type = ""

            if reaction.content_type_id:
                content_type = (
                    f"{reaction.content_type.app_label}."
                    f"{reaction.content_type.model}"
                )

            writer.writerow(
                [
                    reaction.id,
                    getattr(reaction.name, "username", ""),
                    reaction.reaction_type,
                    reaction.message or "",
                    content_type,
                    reaction.object_id,
                    (
                        reaction.timestamp.isoformat()
                        if reaction.timestamp
                        else ""
                    ),
                ]
            )

        return response
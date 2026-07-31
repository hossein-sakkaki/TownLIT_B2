# apps/posts/admin/comment.py

import csv

from django.contrib import admin, messages
from django.db import models
from django.db.models import Q
from django.forms import Textarea
from django.http import HttpResponse

from apps.posts.admin.common import (
    MarkActiveMixin,
    admin_change_link_for_ct_and_pk,
    admin_change_link_for_instance,
)
from apps.posts.admin.filters import (
    ContentAppFilter,
    ContentModelFilter,
    HasRecommentFilter,
    OfficialVideoFilter,
)
from apps.posts.models.comment import Comment


@admin.register(Comment)
class CommentAdmin(MarkActiveMixin, admin.ModelAdmin):
    """
    Moderation panel for comments with generic target information.
    """

    list_display = (
        "user_link",
        "comment_summary",
        "target_link",
        "target_type",
        "is_reply_flag",
        "published_at",
        "is_active",
    )

    list_display_links = (
        "user_link",
        "comment_summary",
        "target_link",
    )

    list_filter = (
        "is_active",
        HasRecommentFilter,
        ContentAppFilter,
        ContentModelFilter,
        OfficialVideoFilter,
        "published_at",
    )

    search_fields = (
        "name__username",
        "name__email",
        "name__name",
        "name__family",
        "object_id",
    )

    formfield_overrides = {
        models.TextField: {
            "widget": Textarea(
                attrs={
                    "rows": 6,
                    "style": (
                        "font-family: ui-monospace, SFMono-Regular, Menlo, "
                        "Consolas, monospace; line-height: 1.5;"
                    ),
                }
            ),
        },
    }

    date_hierarchy = "published_at"
    list_select_related = ("name", "recomment", "content_type")
    autocomplete_fields = ("name", "recomment")
    ordering = ("-published_at",)
    list_per_page = 50

    actions = (
        "make_active",
        "make_inactive",
        "remove_links_in_comments",
        "export_csv_secure",
    )

    @admin.display(description="User", ordering="name__username")
    def user_link(self, obj):
        user = getattr(obj, "name", None)
        return admin_change_link_for_instance(user)

    @admin.display(description="Comment")
    def comment_summary(self, obj):
        text = getattr(obj, "comment", "") or ""

        if not text:
            return "—"

        return f"{text[:80]}…" if len(text) > 80 else text

    @admin.display(description="Is reply?", boolean=True)
    def is_reply_flag(self, obj):
        return bool(getattr(obj, "recomment_id", None))

    @admin.display(description="Target")
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

    @admin.action(
        description="Remove URL protocols from selected comments (anti-spam)"
    )
    def remove_links_in_comments(self, request, queryset):
        suspicious_comments = queryset.filter(
            Q(comment__icontains="http://")
            | Q(comment__icontains="https://")
            | Q(comment__iregex=r"\bwww\.")
        )

        updated = 0

        for comment in suspicious_comments.iterator():
            sanitized_text = comment.comment or ""

            for protocol in ("http://", "https://"):
                sanitized_text = sanitized_text.replace(protocol, "")

            if sanitized_text == comment.comment:
                continue

            comment.comment = sanitized_text
            comment.save(update_fields=["comment"])
            updated += 1

        self.message_user(
            request,
            f"Sanitized {updated} comment(s).",
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
            'attachment; filename="comments.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "user",
                "is_reply",
                "comment",
                "content_type",
                "object_id",
                "published_at",
                "is_active",
            ]
        )

        comments = queryset.select_related(
            "name",
            "content_type",
            "recomment",
        )

        for comment in comments.iterator():
            content_type = ""

            if comment.content_type_id:
                content_type = (
                    f"{comment.content_type.app_label}."
                    f"{comment.content_type.model}"
                )

            writer.writerow(
                [
                    comment.id,
                    getattr(comment.name, "username", ""),
                    bool(comment.recomment_id),
                    comment.comment or "",
                    content_type,
                    comment.object_id,
                    (
                        comment.published_at.isoformat()
                        if comment.published_at
                        else ""
                    ),
                    comment.is_active,
                ]
            )

        return response
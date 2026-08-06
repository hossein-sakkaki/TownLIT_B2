# apps/sanctuary/admin/reviews.py

from __future__ import annotations

from django.contrib import admin

from apps.sanctuary.models import (
    SanctuaryReview,
)

from .helpers import (
    admin_link,
    username_link,
)


@admin.register(
    SanctuaryReview
)
class SanctuaryReviewAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "request_link",
        "reviewer_link",
        "review_status",
        "is_active",
        "is_primary_tradition_match",
        "assigned_at",
        "reviewed_at",
    )

    list_filter = (
        "review_status",
        "is_active",
        "is_primary_tradition_match",
        "assigned_at",
        "reviewed_at",
    )

    search_fields = (
        "=id",
        "=sanctuary_request__id",
        "reviewer__username",
        "reviewer__email",
        "comment",
    )

    ordering = (
        "-reviewed_at",
        "-assigned_at",
        "-id",
    )

    list_select_related = (
        "sanctuary_request",
        "reviewer",
    )

    readonly_fields = (
        "sanctuary_request",
        "reviewer",
        "review_status",
        "comment",
        "is_primary_tradition_match",
        "assigned_at",
        "reviewed_at",
        "is_active",
    )

    fields = readonly_fields
    list_per_page = 75

    @admin.display(
        description="Request",
        ordering="sanctuary_request__id",
    )
    def request_link(
        self,
        obj,
    ):
        return admin_link(
            obj.sanctuary_request,
            f"Sanctuary request {obj.sanctuary_request_id}",
        )

    @admin.display(
        description="Reviewer",
        ordering="reviewer__username",
    )
    def reviewer_link(
        self,
        obj,
    ):
        return username_link(
            obj.reviewer
        )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        # Reviews remain viewable but cannot be modified from admin.
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False
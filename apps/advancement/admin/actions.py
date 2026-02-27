# apps/advancement/admin/actions.py

from django.utils import timezone


def mark_opportunities_under_review(modeladmin, request, queryset):
    """Bulk set stage to UNDER_REVIEW."""
    updated = queryset.update(stage="UNDER_REVIEW", updated_at=timezone.now())
    modeladmin.message_user(request, f"{updated} opportunities marked as Under Review.")
mark_opportunities_under_review.short_description = "Mark selected as Under Review"


def mark_opportunities_closed(modeladmin, request, queryset):
    """Bulk close opportunities."""
    updated = queryset.update(stage="CLOSED", updated_at=timezone.now())
    modeladmin.message_user(request, f"{updated} opportunities marked as Closed.")
mark_opportunities_closed.short_description = "Mark selected as Closed"


def mark_commitments_confirmed(modeladmin, request, queryset):
    """Bulk confirm commitments."""
    updated = queryset.update(status="CONFIRMED")
    modeladmin.message_user(request, f"{updated} commitments marked as Confirmed.")
mark_commitments_confirmed.short_description = "Mark selected commitments as Confirmed"


def mark_commitments_fulfilled(modeladmin, request, queryset):
    """Bulk mark fulfilled (accounting still separate)."""
    updated = queryset.update(status="FULFILLED")
    modeladmin.message_user(request, f"{updated} commitments marked as Fulfilled.")
mark_commitments_fulfilled.short_description = "Mark selected commitments as Fulfilled"


def mark_interactions_done(modeladmin, request, queryset):
    """Bulk close interactions."""
    updated = queryset.update(status="DONE")
    modeladmin.message_user(request, f"{updated} interactions marked as Done.")
mark_interactions_done.short_description = "Mark selected interactions as Done"
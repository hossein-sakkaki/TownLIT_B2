from django.contrib import admin
from .models import CollaborationRequest, JobApplication, ReviewLog
from .constants import (
    COLLABORATION_STATUS_CHOICES,
    JOB_STATUS_CHOICES
)


# ---------------------------
# CollaborationRequest Admin
# ---------------------------
@admin.register(CollaborationRequest)
class CollaborationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "full_name", "email", "collaboration_type", "collaboration_mode",
        "status", "submitted_at", "last_reviewed_by"
    )
    list_filter = ("status", "collaboration_type", "collaboration_mode", "is_active", "submitted_at")
    search_fields = ("full_name", "email", "country", "city", "message")
    readonly_fields = ("submitted_at", "user", "last_reviewed_by")
    autocomplete_fields = ("user", "last_reviewed_by")
    fieldsets = (
        ("User Info", {
            "fields": ("user", "full_name", "email", "phone_number", "country", "city")
        }),
        ("Collaboration", {
            "fields": ("collaboration_type", "collaboration_mode", "availability", "message", "allow_contact")
        }),
        ("Moderation", {
            "fields": ("status", "admin_comment", "admin_note", "last_reviewed_by", "is_active", "submitted_at")
        }),
    )


# ---------------------------
# JobApplication Admin
# ---------------------------
@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "full_name", "email", "position", "status", "submitted_at", "last_reviewed_by"
    )
    list_filter = ("status", "position", "is_active", "submitted_at")
    search_fields = ("full_name", "email", "position", "cover_letter")
    readonly_fields = ("submitted_at", "user", "last_reviewed_by")
    autocomplete_fields = ("user", "last_reviewed_by")
    fieldsets = (
        ("Candidate Info", {
            "fields": ("user", "full_name", "email", "resume", "cover_letter")
        }),
        ("Job Details", {
            "fields": ("position",)
        }),
        ("Moderation", {
            "fields": ("status", "admin_comment", "admin_note", "last_reviewed_by", "is_active", "submitted_at")
        }),
    )


# ---------------------------
# ReviewLog Admin (Read-only)
# ---------------------------
@admin.register(ReviewLog)
class ReviewLogAdmin(admin.ModelAdmin):
    list_display = ("admin", "content_type", "object_id", "action", "created_at")
    list_filter = ("admin", "content_type", "created_at")
    search_fields = ("action", "comment")
    readonly_fields = ("admin", "content_type", "object_id", "action", "comment", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

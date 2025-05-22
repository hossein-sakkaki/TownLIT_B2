from django.contrib import admin
from django.utils.html import format_html

from .models import CollaborationRequest, JobApplication, AccessRequest, ReviewLog
from .utils import create_review_log


# CollaborationRequest Admin ----------------------------------------------------------
@admin.register(CollaborationRequest)
class CollaborationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "display_name", "linked_account", "email", "collaboration_type",
        "collaboration_mode", "status", "submitted_at", "last_reviewed_by"
    )
    list_filter = ("status", "collaboration_type", "collaboration_mode", "is_active", "submitted_at")
    search_fields = ("full_name", "email", "country", "city", "message")
    readonly_fields = (
        "submitted_at", "user", "last_reviewed_by",
        "full_name", "email", "phone_number", "linked_account",
        "country", "city", "message", "collaboration_type", "collaboration_mode", "availability"
    )
    autocomplete_fields = ("user", "last_reviewed_by")
    fieldsets = (
        ("User Info", {
            "fields": ("user", "full_name", "email", "phone_number", "country", "city"),
            "description": "Request info – read-only"
        }),
        ("Collaboration", {
            "fields": ("collaboration_type", "collaboration_mode", "availability", "message", "allow_contact")
        }),
        ("Moderation", {
            "fields": ("status", "admin_comment", "admin_note", "last_reviewed_by", "is_active", "submitted_at")
        }),
    )

    def display_name(self, obj):
        if obj.full_name:
            return obj.full_name
        if obj.user:
            name_parts = filter(None, [obj.user.name, obj.user.family])
            return " ".join(name_parts) or f"User #{obj.user.id}"
        return "Unknown"

    display_name.short_description = "Name"
    display_name.admin_order_field = "full_name"

    def linked_account(self, obj):
        if obj.user:
            url = f"/admin/accounts/customuser/{obj.user.id}/change/"
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return format_html('<span style="color: gray;">Guest Submission</span>')

    linked_account.short_description = "Linked Account"
    
    def save_model(self, request, obj, form, change):
        if request.user.is_staff:
            obj.last_reviewed_by = request.user
        super().save_model(request, obj, form, change)

        if request.user.is_staff and change:
            changed_fields = list(form.changed_data)
            if changed_fields:
                action_parts = []
                for field in changed_fields:
                    old_value = form.initial.get(field, '—')
                    new_value = form.cleaned_data.get(field, '—')
                    action_parts.append(f"{field}: '{old_value}' → '{new_value}'")

                create_review_log(
                    admin_user=request.user,
                    target_instance=obj,
                    action_text="Admin updated: " + ", ".join(action_parts),
                    comment=obj.admin_comment or obj.admin_note or ""
                )


# JobApplication Admin ----------------------------------------------------------
@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "display_name", "linked_account", "email", "position", "status", "submitted_at", "last_reviewed_by"
    )
    list_filter = ("status", "position", "is_active", "submitted_at")
    search_fields = ("full_name", "email", "position", "cover_letter")
    readonly_fields = (
        "submitted_at", "user", "last_reviewed_by",
        "full_name", "email", "resume", "cover_letter", "linked_account"
    )
    autocomplete_fields = ("user", "last_reviewed_by")
    fieldsets = (
        ("Candidate Info", {
            "fields": ("user", "full_name", "email", "resume", "cover_letter", "linked_account"),
            "description": "Application submitted by guest or registered user"
        }),
        ("Job Details", {
            "fields": ("position",)
        }),
        ("Moderation", {
            "fields": ("status", "admin_comment", "admin_note", "last_reviewed_by", "is_active", "submitted_at")
        }),
    )

    def display_name(self, obj):
        if obj.full_name:
            return obj.full_name
        if obj.user:
            name_parts = filter(None, [obj.user.name, obj.user.family])
            return " ".join(name_parts) or f"User #{obj.user.id}"
        return "Unknown"

    display_name.short_description = "Name"
    display_name.admin_order_field = "full_name"

    def linked_account(self, obj):
        if obj.user:
            url = f"/admin/accounts/customuser/{obj.user.id}/change/"
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return format_html('<span style="color: gray;">Guest Submission</span>')

    linked_account.short_description = "Linked Account"

    def save_model(self, request, obj, form, change):
        if request.user.is_staff:
            obj.last_reviewed_by = request.user
        super().save_model(request, obj, form, change)

        if request.user.is_staff and change:
            changed_fields = list(form.changed_data)
            if changed_fields:
                action_parts = []
                for field in changed_fields:
                    old_value = form.initial.get(field, '—')
                    new_value = form.cleaned_data.get(field, '—')
                    action_parts.append(f"{field}: '{old_value}' → '{new_value}'")

                create_review_log(
                    admin_user=request.user,
                    target_instance=obj,
                    action_text="Admin updated: " + ", ".join(action_parts),
                    comment=obj.admin_comment or obj.admin_note or ""
                )


# Access Request Admin ---------------------------------------------------------------
@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = (
        "first_name", "last_name", "email",
        "country", "how_found_us",
        "status", "invite_code_sent", "is_active", "submitted_at"
    )
    list_filter = ("status", "invite_code_sent", "how_found_us", "is_active", "submitted_at")
    search_fields = ("first_name", "last_name", "email", "country", "message")
    readonly_fields = ("submitted_at",)
    ordering = ("-submitted_at",)

    fieldsets = (
        ("Applicant Info", {
            "fields": ("first_name", "last_name", "email", "country", "how_found_us")
        }),
        ("Message", {
            "fields": ("message",)
        }),
        ("Moderation", {
            "fields": ("status", "invite_code_sent", "is_active", "submitted_at")
        }),
    )
    
    
# ReviewLog Admin (Read-only) ----------------------------------------------------------
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

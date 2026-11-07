# apps/accounts/admin/user_admin.py
# TownLIT-Backend
#
# Original Created date: verify from Git history before final commit.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q

from django.utils.html import format_html
from apps.accounts.forms import (
    UserCreationForm, UserChangeForm,
    UserCreationRestrictedForm, UserChangeRestrictedForm,
)
from django.contrib.auth import get_user_model
from apps.profiles.models import Friendship
from apps.sanctuary.models import SanctuaryParticipantProfile

CustomUser = get_user_model()


# SANCTUARY PARTICIPANT PROFILE Inline Admin ----------------------------------------
class SanctuaryParticipationInline(admin.StackedInline):
    model = SanctuaryParticipantProfile
    extra = 1
    can_delete = False
    fk_name = "user"
    fields = (
        "is_participant",
        "is_eligible",
        "eligible_reason",
        "eligible_changed_at",
        "eligible_changed_by",
        "participant_opted_in_at",
        "participant_opted_out_at",
        "settings",
    )
    readonly_fields = ("eligible_changed_at", "eligible_changed_by", "participant_opted_in_at", "participant_opted_out_at")

# Friendship Inline Admin -------------------------------------------------------------    
class FriendshipInline(admin.TabularInline):
    model = Friendship
    fields = ('to_user', 'status', 'created_at')
    extra = 1
    verbose_name_plural = 'Friendships'
    can_delete = True
    fk_name = 'from_user'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(Q(from_user=request.user) | Q(to_user=request.user))
    
    def has_change_permission(self, request, obj=None):
        if obj is None:
            return True
        if isinstance(obj, Friendship):
            return request.user == obj.from_user or request.user == obj.to_user
        return False 


# CUSTOMUSER ADMIN Manager -----------------------------------------------------------
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = [
        "id", "email", "name", "family", "username", "gender", "label",
        "is_verified_identity", "identity_level",
        "pin_security_enabled", "two_factor_enabled",
        "is_member", "is_active", "is_admin", "is_superuser",
        "is_suspended", "is_deleted", "reports_count", "is_account_paused",
        "register_date", "profile_image_thumbnail",
    ]
    list_filter = [
        "is_active", "is_admin", "is_superuser", "gender", "label",
        "is_suspended", "is_deleted", "is_account_paused", "register_date",
    ]
    search_fields = ["email", "username", "mobile_number", "name", "family"]
    readonly_fields = ["register_date", "last_login", "email", "is_verified_identity", "identity_level", "email_change_request_pending"]
    ordering = ["-id"]
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        ("Account Info", {
            "fields": (
                "email", "password", "username", "mobile_number",
                "registration_id", "is_account_paused",
            )
        }),
        ("Personal Info", {
            "fields": (
                "name", "family", "gender", "label", "birthday",
                "country", "city", "primary_language", "secondary_language",
                "image_name", "avatar_version", "register_date",
            )
        }),
        ("Identity Verification (Read-only)", {
            "fields": ("is_verified_identity", "identity_level")
        }),
        ("Security", {
            "fields": (
                "two_factor_enabled", "two_factor_token_expiry",
                "pin_security_enabled",
            )
        }),
        ("Sanctuary / Moderation", {
            "fields": ("is_suspended", "reports_count")
        }),
        ("Expiry / Tokens", {
            "fields": (
                "user_active_code_expiry", "mobile_verification_expiry",
                "reset_token_expiration", "last_email_change",
                "email_change_request_pending",
            )
        }),
        ("Deletion", {
            "fields": ("deletion_requested_at", "is_deleted", "reactivated_at")
        }),
        ("Privacy", {
            "fields": ("show_email", "show_phone_number", "show_country", "show_city")
        }),
        ("Permissions", {
            "fields": ("is_active", "is_member", "is_admin", "is_superuser", "groups", "user_permissions")
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "mobile_number", "name", "family", "username",
                "birthday", "gender", "label", "country", "city",
                "primary_language", "secondary_language",
                "image_name", "password1", "password2",
            ),
        }),
    )

    # If you have FriendshipInline, keep it
    inlines = [SanctuaryParticipationInline]  # e.g. [FriendshipInline]

    def get_form(self, request, obj=None, **kwargs):
        if not request.user.is_superuser:
            kwargs["form"] = UserChangeRestrictedForm if obj is not None else UserCreationRestrictedForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        sets = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return sets
        changed = []
        for title, options in sets:
            options = dict(options)
            options["fields"] = tuple(
                "birthday_masked" if field == "birthday" else field
                for field in options["fields"]
            )
            changed.append((title, options))
        return tuple(changed)

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        return fields if request.user.is_superuser else fields + ("birthday_masked",)

    @admin.display(description="Birthday (restricted)")
    def birthday_masked(self, obj):
        return "[Protected: superuser only]" if obj and obj.birthday_encrypted else "—"

    def get_inline_instances(self, request, obj=None):
        if obj:
            return [inline(self.model, self.admin_site) for inline in self.inlines]
        return []

    @admin.display(description="Email change pending", boolean=True)
    def email_change_request_pending(self, obj):
        return bool(obj and obj.email_change_tokens)

    def profile_image_thumbnail(self, obj):
        if obj.image_name:
            return format_html(
                '<img src="{}" width="30" height="30" style="border-radius:50%;" />',
                obj.image_name.url
            )
        return ""
    profile_image_thumbnail.short_description = "Profile Image"
    


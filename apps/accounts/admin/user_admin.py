# apps/accounts/admin/user_admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q

from django.utils.html import format_html
from apps.accounts.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from apps.profiles.models import Friendship
from apps.sanctuary.models import SanctuaryParticipantProfile

CustomUser = get_user_model()


# SANCTUARY PARTICIPANT PROFILE Inline Admin ----------------------------------------
class SanctuaryParticipationInline(admin.StackedInline):
    model = SanctuaryParticipantProfile
    extra = 0
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
    extra = 0
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
    list_editable = ["is_active", "is_admin", "is_member"]
    search_fields = ["email", "username", "mobile_number", "name", "family"]
    readonly_fields = ["register_date", "last_login", "email", "is_verified_identity", "identity_level"]
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
                "access_pin", "delete_pin",
            )
        }),
        ("Sanctuary / Moderation", {
            "fields": ("is_suspended", "reports_count")
        }),
        ("Expiry / Tokens", {
            "fields": (
                "user_active_code_expiry", "mobile_verification_expiry",
                "reset_token_expiration", "last_email_change",
                "email_change_tokens",
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

    def get_inline_instances(self, request, obj=None):
        if obj:
            return [inline(self.model, self.admin_site) for inline in self.inlines]
        return []

    def profile_image_thumbnail(self, obj):
        if obj.image_name:
            return format_html(
                '<img src="{}" width="30" height="30" style="border-radius:50%;" />',
                obj.image_name.url
            )
        return ""
    profile_image_thumbnail.short_description = "Profile Image"
    

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from colorfield.fields import ColorField
from django.db.models import Q
from django import forms  
from django.utils import timezone
from django.utils.html import format_html

from .forms import UserCreationForm, UserChangeForm
from .models import (
                Address, CustomLabel, SocialMediaType, SocialMediaLink,
                InviteCode, UserDeviceKey,
                IdentityVerification, IdentityAuditLog,
                OrganizationLITShieldEndorsement, LITShieldGrant,
                IdentityGrant
            )
from apps.accounts.services.identity_audit import log_identity_event
from apps.accounts.constants import IA_VERIFY, IA_REVOKE, IA_SOURCE_ADMIN
from apps.accounts.services.identity_verification_service import admin_mark_identity_verified, admin_revoke_identity
from apps.sanctuary.models import SanctuaryParticipantProfile
from apps.profiles.models import Friendship
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# ADDRESS Admin ---------------------------------------------------------------------
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['street_number', 'route', 'locality', 'administrative_area_level_1', 'postal_code', 'country', 'address_type']
    search_fields = ['street_number', 'route', 'locality', 'administrative_area_level_1', 'postal_code', 'country']
    list_filter = ['country', 'locality', 'administrative_area_level_1']
    readonly_fields = ['additional']
    
# CustomLabel Admin ---------------------------------------------------------------------
@admin.register(CustomLabel)
class CustomLabelAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'description', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
    list_filter = ['is_active']
    ordering = ['name']
    formfield_overrides = {
        ColorField: {'widget': forms.TextInput(attrs={'type': 'color'})},
    }

# SOCIAL MEDIA TYPE Admin --------------------------------------------------------------
@admin.register(SocialMediaType)
class SocialMediaTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon_class', 'is_active']
    search_fields = ['name']
    list_editable = ['is_active']
    list_filter = ['is_active']

# URL LINKS Admin -----------------------------------------------------------------------
# @admin.register(SocialMediaLink)
# class SocialMediaLinkAdmin(admin.ModelAdmin):
#     list_display = ['social_media_type', 'link', 'is_active']
#     search_fields = ['link', 'description']
#     list_filter = ['social_media_type', 'is_active']
#     autocomplete_fields = ['social_media_type']


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
    

# Invite Code Admin ---------------------------------------------------------------------
@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'email', 'is_used', 'used_by', 'created_at', 'used_at', 'invite_email_sent', 'invite_email_sent_at']
    search_fields = ['code', 'email']
    list_filter = ['is_used']
    list_editable = ['invite_email_sent']
    

# User Device Key Admin ------------------------------------------------------------------
@admin.register(UserDeviceKey)
class UserDeviceKeyAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'device_name', 'device_id', 'ip_address',
        'location_city', 'location_region', 'location_country',
        'timezone', 'organization', 'postal_code',
        'latitude', 'longitude',
        'last_used', 'is_active',
    )
    list_filter = (
        'is_active', 'location_country', 'location_region', 'organization', 'timezone'
    )
    search_fields = (
        'user__email', 'device_id', 'device_name', 'ip_address',
        'location_city', 'location_region', 'location_country',
        'organization', 'postal_code'
    )
    readonly_fields = (
        'created_at', 'last_used', 'ip_address',
        'location_city', 'location_region', 'location_country',
        'timezone', 'organization', 'postal_code',
        'latitude', 'longitude',
    )
    ordering = ('-last_used',)


# IdentityVerification Admin -----------------------------------------------------------
@admin.register(IdentityVerification)
class IdentityVerificationAdmin(admin.ModelAdmin):
    # Core visibility
    list_display = (
        "user",
        "method",
        "status",
        "level",
        "risk_flag",
        "verified_at",
        "revoked_at",
        "created_at",
    )

    list_filter = (
        "method",
        "status",
        "level",
        "risk_flag",
        "created_at",
    )

    search_fields = (
        "user__email",
        "user__username",
        "provider_reference",
    )

    readonly_fields = (
        "user",
        "method",
        "provider_reference",
        "provider_payload",
        "created_at",
        "updated_at",
        "verified_at",
        "revoked_at",
        "rejected_at",
    )

    fieldsets = (
        ("User", {
            "fields": ("user",)
        }),
        ("Verification Status", {
            "fields": ("method", "status", "level", "risk_flag")
        }),
        ("Provider Data", {
            "classes": ("collapse",),
            "fields": ("provider_reference", "provider_payload")
        }),
        ("Timestamps", {
            "fields": ("created_at", "verified_at", "revoked_at", "rejected_at")
        }),
        ("Admin Notes", {
            "fields": ("notes",)
        }),
    )

    actions = [
        "mark_verified_strong",
        "mark_verified_protected",
        "mark_revoked",
    ]

    # -----------------------------
    # Admin actions
    # -----------------------------
    @admin.action(description="Mark as VERIFIED (STRONG)")
    def mark_verified_strong(self, request, queryset):
        queryset.update(
            status="verified",
            level="strong",
            verified_at=timezone.now(),
            revoked_at=None,
            rejected_at=None,
        )

    @admin.action(description="Mark as VERIFIED (PROTECTED)")
    def mark_verified_protected(self, request, queryset):
        queryset.update(
            status="verified",
            level="protected",
            verified_at=timezone.now(),
            revoked_at=None,
            rejected_at=None,
        )

    @admin.action(description="Revoke identity")
    def mark_revoked(self, request, queryset):
        for iv in queryset:
            prev = iv.status
            iv.status = "revoked"
            iv.revoked_at = timezone.now()
            iv.save()

            log_identity_event(
                user=iv.user,
                identity_verification=iv,
                action=IA_REVOKE,
                source=IA_SOURCE_ADMIN,
                actor=request.user,
                previous_status=prev,
                new_status=iv.status,
                reason="Admin revoke",
            )


# Identity Audit Log Admin --------------------------------------------------------
@admin.register(IdentityAuditLog)
class IdentityAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "action",
        "source",
        "actor",
        "previous_status",
        "new_status",
        "created_at",
    )

    list_filter = (
        "action",
        "source",
        "created_at",
    )

    search_fields = (
        "user__email",
        "actor__email",
        "reason",
    )

    readonly_fields = (
        "user",
        "identity_verification",
        "action",
        "source",
        "actor",
        "reason",
        "previous_status",
        "new_status",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Identity Grant Admin -------------------------------------------------------------
@admin.register(IdentityGrant)
class IdentityGrantAdmin(admin.ModelAdmin):
    list_display = ("user", "level", "source", "is_active", "approved_by", "granted_at", "revoked_at")
    list_filter = ("level", "source", "is_active")
    search_fields = ("user__email", "user__username")
    readonly_fields = ("approved_by", "granted_at", "revoked_at")

    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("Grant", {"fields": ("level", "source", "is_active")}),
        ("Audit", {"fields": ("approved_by", "reason")}),
        ("Timestamps", {"fields": ("granted_at", "revoked_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.approved_by = request.user
        super().save_model(request, obj, form, change)


# LITShield Grant Serializers -----------------------------------------------------------------------
@admin.register(LITShieldGrant)
class LITShieldGrantAdmin(admin.ModelAdmin):
    list_display = (
        "user", "source", "organization", "is_active",
        "approved_by", "granted_at", "revoked_at"
    )

    list_filter = (
        "source", "is_active", "organization"
    )

    search_fields = (
        "user__email", "user__username", "organization__org_name"
    )

    readonly_fields = (
        "approved_by", "granted_at", "revoked_at"
    )

    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("Grant Decision", {"fields": ("is_active", "source", "organization")}),
        ("Admin Notes", {"fields": ("admin_notes",)}),
        ("Audit", {"fields": ("approved_by", "granted_at", "revoked_at")}),
    )

    def save_model(self, request, obj, form, change):
        """
        Custom save:
        - Auto-set approved_by
        - Auto-set granted_at
        - Enforce direct vs org_endorsement logic
        """
        is_new = obj.pk is None

        if is_new:
            obj.approved_by = request.user
            obj.granted_at = timezone.now()

            if obj.organization:
                obj.source = "org_endorsement"
            else:
                obj.source = "direct"

        # Revoke logic
        if not obj.is_active and not obj.revoked_at:
            obj.revoked_at = timezone.now()

        # Reactivation logic
        if obj.is_active:
            obj.revoked_at = None

        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        # ❌ Never allow hard delete (history must remain)
        return False

    def has_change_permission(self, request, obj=None):
        # Allow editing only via form (no bulk edits)
        return True


# LITShield Endorsement Serializers -----------------------------------------------------------------------
@admin.register(OrganizationLITShieldEndorsement)
class OrganizationLITShieldEndorsementAdmin(admin.ModelAdmin):
    list_display = (
        "user", "organization", "referrer_member",
        "approved", "reviewed_by", "created_at"
    )

    list_filter = (
        "approved", "organization", "created_at"
    )

    search_fields = (
        "user__email", "user__username", "organization__org_name"
    )

    readonly_fields = (
        "user", "organization", "referrer_member",
        "reason", "created_at"
    )

    fieldsets = (
        ("Endorsement Request", {"fields": ("user", "organization", "referrer_member", "reason")}),
        ("Review", {"fields": ("approved", "reviewed_by")}),
        ("Timestamps", {"fields": ("created_at", "reviewed_at")}),
    )

    actions = [
        "approve_and_grant_litshield",
        "reject_endorsement",
    ]

    @admin.action(description="Approve & Grant LITShield")
    def approve_and_grant_litshield(self, request, queryset):
        for e in queryset.filter(approved__isnull=True):
            e.approved = True
            e.reviewed_by = request.user
            e.reviewed_at = timezone.now()
            e.save()

            LITShieldGrant.objects.update_or_create(
                user=e.user,
                defaults={
                    "source": "org_endorsement",
                    "organization": e.organization,
                    "approved_by": request.user,
                    "is_active": True,
                }
            )

    @admin.action(description="Reject Endorsement")
    def reject_endorsement(self, request, queryset):
        queryset.filter(approved__isnull=True).update(
            approved=False,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
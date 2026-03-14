# apps/accounts/admin/litshield_admin.py

from django.contrib import admin
from django.utils import timezone

from ..models import (
    OrganizationLITShieldEndorsement,
    LITShieldGrant,
)



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
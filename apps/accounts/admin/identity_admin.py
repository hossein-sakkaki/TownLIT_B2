# apps/accounts/admin/identity_admin.py

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied

from ..models import IdentityVerification, IdentityAuditLog, IdentityGrant
from ..services.identity_verification_service import (
    admin_mark_identity_verified,
    admin_revoke_identity,
    admin_unverify_identity,
)

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

    # Lock sensitive state fields in admin form
    readonly_fields = (
        "user",
        "method",
        "status",
        "level",
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
            "fields": ("created_at", "updated_at", "verified_at", "revoked_at", "rejected_at")
        }),
        ("Admin Notes", {
            "fields": ("notes",)
        }),
    )

    actions = [
        "mark_verified_strong",
        "mark_verified_protected",
        "mark_revoked",
        "mark_unverified_fully",
    ]

    def save_model(self, request, obj, form, change):
        """
        Block direct state edits from admin form.
        Only allow safe note/risk updates.
        """
        if not change:
            super().save_model(request, obj, form, change)
            return

        original = type(obj).objects.get(pk=obj.pk)

        protected_fields = (
            "method",
            "status",
            "level",
            "verified_at",
            "revoked_at",
            "rejected_at",
        )

        for field in protected_fields:
            setattr(obj, field, getattr(original, field))

        super().save_model(request, obj, form, change)

    @admin.action(description="Mark as VERIFIED (STRONG)")
    def mark_verified_strong(self, request, queryset):
        # Verify selected users with strong level
        success_count = 0

        for iv in queryset.select_related("user"):
            try:
                admin_mark_identity_verified(
                    actor=request.user,
                    target_user=iv.user,
                    level="strong",
                    reason="Admin marked identity as verified (strong)",
                )
                success_count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Failed to verify {iv.user}: {exc}",
                    level=messages.ERROR,
                )

        if success_count:
            self.message_user(
                request,
                f"{success_count} identity record(s) marked as verified (strong).",
                level=messages.SUCCESS,
            )

    @admin.action(description="Mark as VERIFIED (PROTECTED)")
    def mark_verified_protected(self, request, queryset):
        # Verify selected users with protected level
        success_count = 0

        for iv in queryset.select_related("user"):
            try:
                admin_mark_identity_verified(
                    actor=request.user,
                    target_user=iv.user,
                    level="protected",
                    reason="Admin marked identity as verified (protected)",
                )
                success_count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Failed to verify {iv.user}: {exc}",
                    level=messages.ERROR,
                )

        if success_count:
            self.message_user(
                request,
                f"{success_count} identity record(s) marked as verified (protected).",
                level=messages.SUCCESS,
            )

    @admin.action(description="Revoke identity")
    def mark_revoked(self, request, queryset):
        # Revoke selected identities
        success_count = 0

        for iv in queryset.select_related("user"):
            try:
                admin_revoke_identity(
                    actor=request.user,
                    target_user=iv.user,
                    reason="Admin revoke",
                )
                success_count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Failed to revoke {iv.user}: {exc}",
                    level=messages.ERROR,
                )

        if success_count:
            self.message_user(
                request,
                f"{success_count} identity record(s) revoked.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Fully unverify identity (revoke verification + grants)")
    def mark_unverified_fully(self, request, queryset):
        """
        Fully remove verified state from selected users.
        This revokes both IdentityVerification and any active IdentityGrant rows.
        """
        success_count = 0

        for iv in queryset.select_related("user"):
            try:
                admin_unverify_identity(
                    actor=request.user,
                    target_user=iv.user,
                    reason="Admin fully unverified identity",
                )
                success_count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Failed to fully unverify {iv.user}: {exc}",
                    level=messages.ERROR,
                )

        if success_count:
            self.message_user(
                request,
                f"{success_count} identity record(s) fully unverified.",
                level=messages.SUCCESS,
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
        # Audit logs are write-once
        return False

    def has_change_permission(self, request, obj=None):
        # Audit logs are immutable
        return False

    def has_delete_permission(self, request, obj=None):
        # Audit logs should not be deleted
        return False


# Identity Grant Admin -------------------------------------------------------------
@admin.register(IdentityGrant)
class IdentityGrantAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "level",
        "source",
        "is_active",
        "approved_by",
        "granted_at",
        "revoked_at",
    )

    list_filter = (
        "level",
        "source",
        "is_active",
    )

    search_fields = (
        "user__email",
        "user__username",
    )

    # Lock sensitive grant fields
    readonly_fields = (
        "approved_by",
        "granted_at",
        "revoked_at",
        "is_active",
    )

    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("Grant", {"fields": ("level", "source", "is_active")}),
        ("Audit", {"fields": ("approved_by", "reason")}),
        ("Timestamps", {"fields": ("granted_at", "revoked_at")}),
    )

    actions = ["revoke_selected_grants"]

    def has_delete_permission(self, request, obj=None):
        # Prevent hard delete from admin
        return False

    def save_model(self, request, obj, form, change):
        """
        Limit direct grant edits.
        Grant lifecycle should be controlled by service layer.
        """
        if not change:
            # Track admin approver on create
            obj.approved_by = request.user
            super().save_model(request, obj, form, change)
            return

        original = type(obj).objects.get(pk=obj.pk)

        # Block direct activation/deactivation
        obj.is_active = original.is_active
        obj.revoked_at = original.revoked_at
        obj.approved_by = original.approved_by
        obj.granted_at = original.granted_at

        super().save_model(request, obj, form, change)

    @admin.action(description="Revoke selected grants")
    def revoke_selected_grants(self, request, queryset):
        """
        Revoke active identity grants instead of deleting them.
        """
        from django.utils import timezone

        success_count = 0
        now = timezone.now()

        for grant in queryset.select_related("user", "approved_by"):
            try:
                if not grant.is_active:
                    continue

                grant.is_active = False
                grant.revoked_at = now
                grant.save(update_fields=["is_active", "revoked_at"])

                IdentityAuditLog.objects.create(
                    user=grant.user,
                    identity_verification=getattr(grant.user, "identity_verification", None),
                    action="revoked",
                    source="admin",
                    actor=request.user,
                    reason="Admin revoked identity grant",
                    previous_status="grant_active",
                    new_status="grant_revoked",
                    metadata={
                        "scope": "identity_grant",
                        "grant_id": grant.id,
                        "grant_level": grant.level,
                        "grant_source": grant.source,
                    },
                )

                success_count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Failed to revoke grant for {grant.user}: {exc}",
                    level=messages.ERROR,
                )

        if success_count:
            self.message_user(
                request,
                f"{success_count} grant(s) revoked.",
                level=messages.SUCCESS,
            )
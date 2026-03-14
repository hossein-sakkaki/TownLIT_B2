# apps/accounts/admin/townlit_verification_admin.py

from django.contrib import admin, messages

from apps.accounts.models.townlit_verification import (
    TownlitVerificationGrant,
    TownlitVerificationAuditLog,
)
from apps.accounts.services.townlit_verification_service import (
    admin_revoke_townlit_verified,
)


@admin.register(TownlitVerificationAuditLog)
class TownlitVerificationAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "member",
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
        "member__user__email",
        "member__user__username",
        "actor__email",
        "reason",
    )

    readonly_fields = (
        "member",
        "user",
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


@admin.register(TownlitVerificationGrant)
class TownlitVerificationGrantAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "source",
        "is_active",
        "approved_by",
        "granted_at",
        "revoked_at",
    )

    list_filter = (
        "source",
        "is_active",
    )

    search_fields = (
        "member__user__email",
        "member__user__username",
    )

    readonly_fields = (
        "member",
        "source",
        "reason",
        "approved_by",
        "granted_at",
        "revoked_at",
        "is_active",
    )

    fieldsets = (
        ("Member", {"fields": ("member",)}),
        ("Grant", {"fields": ("source", "is_active")}),
        ("Audit", {"fields": ("approved_by", "reason")}),
        ("Timestamps", {"fields": ("granted_at", "revoked_at")}),
    )

    actions = ["revoke_selected_grants"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Revoke selected TownLIT grants")
    def revoke_selected_grants(self, request, queryset):
        success_count = 0

        for grant in queryset.select_related("member", "member__user", "approved_by"):
            try:
                if not grant.is_active:
                    continue

                admin_revoke_townlit_verified(
                    actor=request.user,
                    target_member=grant.member,
                    reason="Admin revoked TownLIT Gold from grant admin",
                )
                success_count += 1

            except Exception as exc:
                self.message_user(
                    request,
                    f"Failed to revoke grant for {grant.member}: {exc}",
                    level=messages.ERROR,
                )

        if success_count:
            self.message_user(
                request,
                f"{success_count} TownLIT grant(s) revoked.",
                level=messages.SUCCESS,
            )
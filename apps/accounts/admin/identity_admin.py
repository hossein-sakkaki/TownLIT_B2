# apps/accounts/admin/identity_admin.py
# TownLIT-Backend
#
# Original Created date: verify from Git history before final commit.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django import forms
from django.utils.html import format_html
import json
import logging

from ..models import IdentityVerification, IdentityAuditLog, IdentityGrant
from ..services.identity_verification_service import (
    admin_mark_identity_verified,
    admin_revoke_identity,
    admin_unverify_identity,
)

logger = logging.getLogger(__name__)

class IdentityVerificationAdminForm(forms.ModelForm):
    notes = forms.CharField(required=False, widget=forms.Textarea, label="Admin notes")

    class Meta:
        model = IdentityVerification
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        super().__init__(*args, **kwargs)
        if instance is not None and instance.pk:
            self.fields["notes"].initial = instance.notes or ""


class IdentityVerificationRestrictedAdminForm(forms.ModelForm):
    class Meta:
        model = IdentityVerification
        fields = "__all__"


# IdentityVerification Admin -----------------------------------------------------------
@admin.register(IdentityVerification)
class IdentityVerificationAdmin(admin.ModelAdmin):
    form = IdentityVerificationAdminForm
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
        "provider_payload_view",
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
            "fields": ("provider_reference", "provider_payload_view")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at", "verified_at", "revoked_at", "rejected_at")
        }),
        ("Admin Notes", {
            "fields": ("notes",)
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        if not request.user.is_superuser:
            kwargs["form"] = IdentityVerificationRestrictedAdminForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if not request.user.is_superuser:
            result = []
            for title, options in fieldsets:
                options = dict(options)
                options["fields"] = tuple(
                    "notes_masked" if value == "notes" else
                    "provider_reference_masked" if value == "provider_reference" else value
                    for value in options["fields"]
                )
                result.append((title, options))
            return result
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            return fields + ("notes_masked", "provider_reference_masked", "risk_flag")
        return fields

    def get_search_fields(self, request):
        fields = tuple(super().get_search_fields(request))
        if not request.user.is_superuser:
            return tuple(name for name in fields if name != "provider_reference")
        return fields

    @admin.display(description="Provider reference (restricted)")
    def provider_reference_masked(self, obj):
        return "[Protected: superuser only]" if obj and obj.provider_reference else "—"

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field=from_field)
        if obj is not None:
            obj._dp_admin_can_reveal = bool(request.user.is_superuser)
            obj._dp_admin_actor_id = request.user.pk
        return obj

    @admin.display(description="Provider payload (restricted)")
    def provider_payload_view(self, obj):
        if not obj:
            return "—"
        if not getattr(obj, "_dp_admin_can_reveal", False):
            return "[Protected: superuser only]"
        logger.info(
            "Identity provider payload viewed in admin actor_id=%s iv_id=%s",
            getattr(obj, "_dp_admin_actor_id", None), obj.pk,
        )
        payload = obj.provider_payload
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) if payload is not None else "—"

    @admin.display(description="Admin notes (restricted)")
    def notes_masked(self, obj):
        return "[Protected: superuser only]" if obj and obj.notes_encrypted else "—"

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

        if request.user.is_superuser and "notes" in form.cleaned_data:
            obj.notes = form.cleaned_data["notes"] or None
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
                    f"Identity operation failed for record {iv.pk}.",
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
                    f"Identity operation failed for record {iv.pk}.",
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
                    f"Identity operation failed for record {iv.pk}.",
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
                    f"Identity operation failed for record {iv.pk}.",
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
        "user__username",
        "actor__username",
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

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        if request.user.is_superuser:
            return fields
        return tuple(
            "reason_masked" if field == "reason" else
            "metadata_masked" if field == "metadata" else field
            for field in fields
        )

    @admin.display(description="Reason (restricted)")
    def reason_masked(self, obj):
        return "[Protected: superuser only]" if obj and obj.reason_encrypted else "—"

    @admin.display(description="Metadata (restricted)")
    def metadata_masked(self, obj):
        return "[Protected: superuser only]" if obj and obj.metadata_encrypted else "—"

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field=from_field)
        if obj is not None and request.user.is_superuser:
            logger.info("Identity audit private view actor_id=%s audit_id=%s",
                        request.user.pk, obj.pk)
        return obj

    def has_add_permission(self, request):
        # Audit logs are write-once
        return False

    def has_change_permission(self, request, obj=None):
        # Audit logs are immutable
        return False

    # def has_delete_permission(self, request, obj=None):
    #     # Audit logs should not be deleted
    #     return False


# Protected identity grant reason remains editable by authorized administrators.
class IdentityGrantProtectedForm(forms.ModelForm):
    reason = forms.CharField(required=True, widget=forms.Textarea)

    class Meta:
        model = IdentityGrant
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["reason"].initial = self.instance.reason or ""

    def save(self, commit=True):
        grant = super().save(commit=False)
        grant.reason = self.cleaned_data["reason"]
        if commit:
            grant.save()
            self.save_m2m()
        return grant


class IdentityGrantRestrictedForm(forms.ModelForm):
    class Meta:
        model = IdentityGrant
        fields = "__all__"


# Identity Grant Admin -------------------------------------------------------------
@admin.register(IdentityGrant)
class IdentityGrantAdmin(admin.ModelAdmin):
    form = IdentityGrantProtectedForm

    def get_form(self, request, obj=None, **kwargs):
        if not request.user.is_superuser:
            kwargs["form"] = IdentityGrantRestrictedForm
        return super().get_form(request, obj, **kwargs)
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

    def get_fieldsets(self, request, obj=None):
        result = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return result
        changed = []
        for title, options in result:
            options = dict(options)
            options["fields"] = tuple(
                "reason_masked" if field == "reason" else field
                for field in options["fields"]
            )
            changed.append((title, options))
        return tuple(changed)

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        return fields if request.user.is_superuser else fields + ("reason_masked",)

    @admin.display(description="Grant reason (restricted)")
    def reason_masked(self, obj):
        return "[Protected: superuser only]" if obj and obj.reason_encrypted else "—"

    actions = ["revoke_selected_grants"]

    # def has_delete_permission(self, request, obj=None):
    #     # Prevent hard delete from admin
    #     return False

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field=from_field)
        if obj is not None and request.user.is_superuser:
            logger.info("Identity grant private view actor_id=%s grant_id=%s",
                        request.user.pk, obj.pk)
        return obj

    def save_model(self, request, obj, form, change):
        """
        Limit direct grant edits.
        Grant lifecycle should be controlled by service layer.
        """
        if request.user.is_superuser and "reason" in form.cleaned_data:
            obj.reason = form.cleaned_data["reason"]
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
                    f"Identity grant action failed for record {grant.pk}.",
                    level=messages.ERROR,
                )

        if success_count:
            self.message_user(
                request,
                f"{success_count} grant(s) revoked.",
                level=messages.SUCCESS,
            )

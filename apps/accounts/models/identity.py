# apps/accounts/models/identity.py

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.constants.identity_audit import (
    IDENTITY_AUDIT_ACTION_CHOICES,
    IDENTITY_AUDIT_SOURCE_CHOICES,
)
from apps.accounts.constants.identity_verification import (
    IDENTITY_VERIFICATION_LEVEL_CHOICES,
    IDENTITY_VERIFICATION_METHOD_CHOICES,
    IDENTITY_VERIFICATION_STATUS_CHOICES,
    IV_STATUS_PENDING,
    IV_STATUS_REVOKED,
    IV_STATUS_VERIFIED,
)


class IdentityVerification(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="identity_verification",
        db_index=True,
    )

    method = models.CharField(max_length=20, choices=IDENTITY_VERIFICATION_METHOD_CHOICES, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=IDENTITY_VERIFICATION_STATUS_CHOICES,
        default=IV_STATUS_PENDING,
        db_index=True,
    )
    level = models.CharField(max_length=20, choices=IDENTITY_VERIFICATION_LEVEL_CHOICES, db_index=True)

    provider_reference = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    provider_payload = models.JSONField(null=True, blank=True)

    verified_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    rejected_at = models.DateTimeField(null=True, blank=True, db_index=True)

    risk_flag = models.BooleanField(default=False, db_index=True)
    notes = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Identity Verification"
        verbose_name_plural = "Identity Verifications"

    def __str__(self):
        return f"IV({self.user_id}) {self.method}:{self.status}:{self.level}"

    def mark_verified(self, level=None):
        self.status = IV_STATUS_VERIFIED
        if level:
            self.level = level
        self.verified_at = timezone.now()
        self.revoked_at = None
        self.rejected_at = None
        self.save(update_fields=["status", "level", "verified_at", "revoked_at", "rejected_at", "updated_at"])

    def mark_revoked(self, reason=None):
        self.status = IV_STATUS_REVOKED
        self.revoked_at = timezone.now()
        if reason:
            self.notes = (reason[:1000] if isinstance(reason, str) else str(reason)[:1000])
        self.save(update_fields=["status", "revoked_at", "notes", "updated_at"])


class IdentityGrant(models.Model):
    SOURCE_ADMIN = "admin"
    SOURCE_SYSTEM = "system"

    SOURCE_CHOICES = [
        (SOURCE_ADMIN, "TownLIT Admin"),
        (SOURCE_SYSTEM, "System"),
    ]

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="identity_grants")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    level = models.CharField(max_length=20, choices=IDENTITY_VERIFICATION_LEVEL_CHOICES)
    reason = models.TextField()
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_identity_grants",
    )
    is_active = models.BooleanField(default=True)
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Identity Grant"
        verbose_name_plural = "Identity Grants"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_active=True),
                name="unique_active_identity_grant_per_user",
            )
        ]

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])


class IdentityAuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="identity_audit_logs",
        db_index=True,
    )
    identity_verification = models.ForeignKey(
        "accounts.IdentityVerification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    action = models.CharField(max_length=20, choices=IDENTITY_AUDIT_ACTION_CHOICES, db_index=True)
    source = models.CharField(max_length=20, choices=IDENTITY_AUDIT_SOURCE_CHOICES, db_index=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performed_identity_audits",
    )
    reason = models.CharField(max_length=1000, null=True, blank=True)

    previous_status = models.CharField(max_length=20, null=True, blank=True)
    new_status = models.CharField(max_length=20, null=True, blank=True)

    metadata = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Identity Audit Log"
        verbose_name_plural = "Identity Audit Logs"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user_id} {self.action} via {self.source} @ {self.created_at}"
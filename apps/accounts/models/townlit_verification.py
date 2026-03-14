from django.conf import settings
from django.db import models
from django.utils import timezone


class TownlitVerificationGrant(models.Model):
    SOURCE_ADMIN = "admin"
    SOURCE_SYSTEM = "system"

    SOURCE_CHOICES = [
        (SOURCE_ADMIN, "TownLIT Admin"),
        (SOURCE_SYSTEM, "System"),
    ]

    id = models.BigAutoField(primary_key=True)

    member = models.ForeignKey(
        "profiles.Member",
        on_delete=models.CASCADE,
        related_name="townlit_verification_grants",
    )

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    reason = models.TextField()

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_townlit_verification_grants",
    )

    is_active = models.BooleanField(default=True)
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "TownLIT Verification Grant"
        verbose_name_plural = "TownLIT Verification Grants"
        constraints = [
            models.UniqueConstraint(
                fields=["member"],
                condition=models.Q(is_active=True),
                name="unique_active_townlit_verification_grant_per_member",
            )
        ]

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])


class TownlitVerificationAuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)

    member = models.ForeignKey(
        "profiles.Member",
        on_delete=models.CASCADE,
        related_name="townlit_verification_audit_logs",
        db_index=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="townlit_verification_logs",
        db_index=True,
    )

    action = models.CharField(max_length=30, db_index=True)
    source = models.CharField(max_length=20, db_index=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performed_townlit_verification_audits",
    )

    reason = models.CharField(max_length=1000, null=True, blank=True)
    previous_status = models.CharField(max_length=30, null=True, blank=True)
    new_status = models.CharField(max_length=30, null=True, blank=True)

    metadata = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "TownLIT Verification Audit Log"
        verbose_name_plural = "TownLIT Verification Audit Logs"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.member_id} {self.action} via {self.source} @ {self.created_at}"
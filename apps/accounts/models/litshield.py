# apps/accounts/models/litshield.py

from django.conf import settings
from django.db import models


class LITShieldGrant(models.Model):
    """
    Controls access to PIN / LITShield features.
    NOT related to identity or spiritual verification.
    """

    DIRECT = "direct"
    ORG_ENDORSEMENT = "org_endorsement"

    GRANT_SOURCE_CHOICES = [
        (DIRECT, "Direct TownLIT Decision"),
        (ORG_ENDORSEMENT, "Organization Endorsement"),
    ]

    id = models.BigAutoField(primary_key=True)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="litshield_grant",
        db_index=True,
    )

    source = models.CharField(
        max_length=20,
        choices=GRANT_SOURCE_CHOICES,
        db_index=True,
    )

    organization = models.ForeignKey(
        "profilesOrg.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="litshield_endorsements",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="litshield_requests",
        help_text="Admin or organization owner who initiated this",
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="litshield_approvals",
        help_text="TownLIT admin who approved",
    )

    is_active = models.BooleanField(default=True, db_index=True)

    admin_notes = models.TextField(null=True, blank=True)

    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "LITShield Grant"
        verbose_name_plural = "LITShield Grants"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_active=True),
                name="unique_active_litshield_per_user",
            )
        ]

    def __str__(self):
        return f"LITShield → {self.user_id} ({self.source})"


class OrganizationLITShieldEndorsement(models.Model):
    from apps.profilesOrg.models import Organization

    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="litshield_endorsement_requests",
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="litshield_grants",
    )

    referrer_member = models.ForeignKey(
        "profiles.Member",
        on_delete=models.PROTECT,
        help_text="Member submitting endorsement",
    )

    reason = models.TextField()

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="litshield_reviews",
    )

    approved = models.BooleanField(null=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "organization")
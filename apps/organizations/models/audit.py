# apps/organizations/models/audit.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.conf import settings
from django.db import models

from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationAuditSource,
)


class OrganizationAuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    action = models.CharField(
        max_length=60,
        choices=OrganizationAuditAction.choices,
        db_index=True,
    )
    source = models.CharField(
        max_length=20,
        choices=OrganizationAuditSource.choices,
        default=OrganizationAuditSource.SERVICE,
        db_index=True,
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_audit_actions",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_audit_targets",
    )

    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    membership_request = models.ForeignKey(
        "organizations.OrganizationMembershipRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    role_assignment = models.ForeignKey(
        "organizations.OrganizationRoleAssignment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    verification_case = models.ForeignKey(
        "organizations.OrganizationVerificationCase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    relationship = models.ForeignKey(
        "organizations.OrganizationRelationship",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    governance_proposal = models.ForeignKey(
        "organizations.OrganizationGovernanceProposal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    module_activation = models.ForeignKey(
        "organizations.OrganizationModuleActivation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        verbose_name = "Organization Audit Log"
        verbose_name_plural = "Organization Audit Logs"
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=[
                    "organization",
                    "action",
                    "created_at",
                ]
            ),
        ]

    def __str__(self):
        return (
            f"{self.organization_id}:"
            f"{self.action}:"
            f"{self.created_at}"
        )

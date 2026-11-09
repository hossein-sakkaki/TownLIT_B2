# apps/ai_gateway/models.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Gateway metadata only. No human users, domain records or credentials."""

import uuid

from django.db import models


class ServicePrincipal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_id = models.CharField(
        max_length=16,
        choices=[
            (name, name)
            for name in ("eli", "phoebe", "silas", "lydia", "joanna", "micah", "chloe")
        ],
    )
    environment = models.CharField(max_length=32)
    active = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class OfficeOrganizationBinding(models.Model):
    """Provisional identifiers, never proof of authoritative domain ownership.

    No binding service or domain selector exists in B1. A later checkpoint must
    resolve Backend Organization.public_id and independently scoped domain FKs.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    environment = models.CharField(max_length=32)
    office_organization_id = models.UUIDField()
    backend_organization_id = models.UUIDField()
    active = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["environment", "office_organization_id"],
                name="aig_org_mapping_uq",
            )
        ]


class OperationGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    principal = models.ForeignKey(ServicePrincipal, on_delete=models.PROTECT)
    organization = models.ForeignKey(
        OfficeOrganizationBinding, on_delete=models.PROTECT
    )
    operation = models.CharField(max_length=80)
    version = models.PositiveSmallIntegerField()
    # Exact metadata record only; no wildcard, implicit collection or ORM target.
    scope_ref = models.UUIDField()
    active = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "principal",
                    "organization",
                    "operation",
                    "version",
                    "scope_ref",
                ],
                name="aig_grant_scope_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="aig_grant_version_ck"
            ),
        ]


class RequestNonce(models.Model):
    principal = models.ForeignKey(ServicePrincipal, on_delete=models.PROTECT)
    purpose = models.CharField(
        max_length=16, choices=[("request", "request"), ("assertion", "assertion")]
    )
    digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["principal", "purpose", "digest"],
                name="aig_nonce_once_uq",
            )
        ]
        indexes = [models.Index(fields=["expires_at"], name="aig_nonce_exp_idx")]


class IdempotencyReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    principal = models.ForeignKey(ServicePrincipal, on_delete=models.PROTECT)
    organization = models.ForeignKey(
        OfficeOrganizationBinding, on_delete=models.PROTECT
    )
    operation = models.CharField(max_length=80)
    version = models.PositiveSmallIntegerField()
    scope_ref = models.UUIDField()
    key_digest = models.CharField(max_length=64)
    payload_digest = models.CharField(max_length=64)
    canonicalization_version = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "principal",
                    "organization",
                    "operation",
                    "version",
                    "key_digest",
                ],
                name="aig_receipt_key_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "created_at"], name="aig_receipt_org_idx"
            )
        ]


class AuditEvent(models.Model):
    """No arbitrary text/JSON payload, request paths, tokens or exception text."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_id = models.UUIDField()
    correlation_id = models.UUIDField()
    principal = models.ForeignKey(ServicePrincipal, null=True, on_delete=models.PROTECT)
    organization = models.ForeignKey(
        OfficeOrganizationBinding, null=True, on_delete=models.PROTECT
    )
    receipt = models.ForeignKey(IdempotencyReceipt, null=True, on_delete=models.PROTECT)
    code = models.CharField(
        max_length=32,
        choices=[
            (name, name)
            for name in (
                "access_denied",
                "metadata_reserved",
                "metadata_replayed",
                "grant_revoked",
            )
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["organization", "created_at"], name="aig_audit_org_idx"
            )
        ]

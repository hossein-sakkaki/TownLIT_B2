# apps/ai_gateway/receipts.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Atomic metadata receipts only. Never execute a caller callback/domain effect."""

import hashlib
import re
from uuid import UUID, uuid4

from django.db import DatabaseError, transaction

from .errors import GatewayDenied
from .models import AuditEvent, IdempotencyReceipt, OperationGrant, ServicePrincipal
from .policy import require_metadata_permission
from .security import VerifiedIdentity
from .validation import metadata_envelope


def reserve_metadata_receipt(identity, *, key, body):
    if not isinstance(identity, VerifiedIdentity):
        raise GatewayDenied()
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", key):
        raise GatewayDenied("invalid_request")
    envelope, digest = metadata_envelope(body)
    try:
        with transaction.atomic():
            # All metadata writers lock principal -> organization -> grant -> receipt.
            principal, organization, _ = require_metadata_permission(
                identity,
                "gateway.capabilities",
                1,
                identity.principal_id,
                lock=True,
            )
            receipt, created = IdempotencyReceipt.objects.get_or_create(
                principal=principal,
                organization=organization,
                operation="gateway.capabilities",
                version=1,
                key_digest=hashlib.sha256(key.encode("ascii")).hexdigest(),
                defaults={"scope_ref": principal.pk, "payload_digest": digest},
            )
            if (
                receipt.payload_digest != digest
                or receipt.scope_ref != principal.pk
                or receipt.canonicalization_version != 1
            ):
                raise GatewayDenied("idempotency_conflict")
            AuditEvent.objects.create(
                request_id=uuid4(),
                correlation_id=envelope["correlation_id"],
                principal=principal,
                organization=organization,
                receipt=receipt,
                code="metadata_reserved" if created else "metadata_replayed",
            )
            return receipt.pk, not created
    except DatabaseError:
        raise GatewayDenied("security_unavailable") from None


def revoke_grant(grant_id: UUID):
    """Internal maintainer primitive; no public provisioning/revocation endpoint."""
    from django.utils import timezone

    if not isinstance(grant_id, UUID):
        raise GatewayDenied()
    try:
        principal_id = OperationGrant.objects.values_list(
            "principal_id", flat=True
        ).get(pk=grant_id)
        with transaction.atomic():
            ServicePrincipal.objects.select_for_update().get(pk=principal_id)
            grant = OperationGrant.objects.select_for_update().get(pk=grant_id)
            if grant.principal_id != principal_id:
                raise GatewayDenied()
            grant.active = False
            grant.revoked_at = timezone.now()
            grant.save(update_fields=["active", "revoked_at"])
            AuditEvent.objects.create(
                request_id=uuid4(),
                correlation_id=uuid4(),
                principal_id=principal_id,
                organization_id=grant.organization_id,
                code="grant_revoked",
            )
    except (OperationGrant.DoesNotExist, ServicePrincipal.DoesNotExist):
        raise GatewayDenied() from None
    except DatabaseError:
        raise GatewayDenied("security_unavailable") from None

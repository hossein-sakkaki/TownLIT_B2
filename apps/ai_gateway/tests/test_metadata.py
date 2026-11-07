# apps/ai_gateway/tests/test_metadata.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

import json
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.db import IntegrityError, OperationalError, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.ai_gateway.errors import GatewayDenied
from apps.ai_gateway.models import (
    AuditEvent, IdempotencyReceipt, OfficeOrganizationBinding,
    OperationGrant, RequestNonce, ServicePrincipal,
)
from apps.ai_gateway.policy import require_metadata_permission
from apps.ai_gateway.receipts import reserve_metadata_receipt, revoke_grant
from apps.ai_gateway.replay import reserve_nonce
from apps.ai_gateway.security import VerifiedIdentity
from apps.ai_gateway.validation import metadata_envelope


def fixture():
    principal = ServicePrincipal.objects.create(agent_id="phoebe", environment="synthetic", active=True)
    organization = OfficeOrganizationBinding.objects.create(
        environment="synthetic", office_organization_id=uuid4(),
        backend_organization_id=uuid4(), active=True,
    )
    grant = OperationGrant.objects.create(
        principal=principal, organization=organization, operation="gateway.capabilities",
        version=1, scope_ref=principal.pk, active=True,
        expires_at=timezone.now() + timedelta(hours=1),
    )
    identity = VerifiedIdentity(
        principal.pk, principal.agent_id, organization.office_organization_id,
        organization.backend_organization_id, frozenset({"gateway.metadata"}),
    )
    body = json.dumps({"schema_version": 1, "purpose": "gateway_metadata", "correlation_id": str(uuid4())}).encode()
    return principal, organization, grant, identity, body


@override_settings(AI_GATEWAY_ENABLED=True)
class MetadataTests(TestCase):
    def setUp(self):
        self.principal, self.organization, self.grant, self.identity, self.body = fixture()

    def authorize(self, identity=None, operation="gateway.capabilities", version=1, scope_ref=None):
        return require_metadata_permission(
            identity or self.identity, operation, version, scope_ref or self.principal.pk,
        )

    def test_exact_current_metadata_grant_only(self):
        self.assertEqual(self.authorize()[2].pk, self.grant.pk)
        for operation in ("unknown", "accounting.lookup", "advancement.read", "gateway.capabilities.v2"):
            with self.subTest(operation=operation), self.assertRaises(GatewayDenied):
                self.authorize(operation=operation)
        for version in (0, 2, True, "1"):
            with self.subTest(version=version), self.assertRaises(GatewayDenied):
                self.authorize(version=version)

    def test_missing_unknown_identity_scope_and_environment_deny(self):
        for identity in (None, {}, replace(self.identity, principal_id=uuid4()),
                         replace(self.identity, agent_id="micah"),
                         replace(self.identity, scopes=frozenset()),
                         replace(self.identity, office_organization_id=uuid4()),
                         replace(self.identity, backend_organization_id=uuid4())):
            with self.subTest(identity=identity), self.assertRaises(GatewayDenied):
                require_metadata_permission(identity, "gateway.capabilities", 1, self.principal.pk)
        with override_settings(AI_GATEWAY_ENVIRONMENT=""), self.assertRaises(GatewayDenied):
            self.authorize()
        with override_settings(AI_GATEWAY_ENVIRONMENT="other"), self.assertRaises(GatewayDenied):
            self.authorize()

    def test_disabled_denies_even_complete_metadata_configuration(self):
        with override_settings(AI_GATEWAY_ENABLED=False), self.assertRaises(GatewayDenied):
            self.authorize()

    def test_cross_record_and_cross_organization_denied(self):
        other_principal, org, _, other, _ = fixture()
        for identity, scope in ((self.identity, other_principal.pk),
                                (replace(self.identity, office_organization_id=org.office_organization_id,
                                         backend_organization_id=org.backend_organization_id), self.principal.pk),
                                (other, self.principal.pk)):
            with self.subTest(scope=scope), self.assertRaises(GatewayDenied):
                self.authorize(identity=identity, scope_ref=scope)

    def test_chloe_and_unregistered_agents_denied_even_with_bad_grant(self):
        for agent in ("chloe", "eli", "lydia", "joanna", "unknown"):
            ServicePrincipal.objects.filter(pk=self.principal.pk).update(agent_id=agent)
            with self.subTest(agent=agent), self.assertRaises(GatewayDenied):
                self.authorize(identity=replace(self.identity, agent_id=agent))

    def test_missing_expired_inactive_and_revoked_grants_deny(self):
        for changes in ({"active": False}, {"expires_at": timezone.now() - timedelta(seconds=1)},
                        {"revoked_at": timezone.now()}):
            with transaction.atomic():
                OperationGrant.objects.filter(pk=self.grant.pk).update(**changes)
                with self.assertRaises(GatewayDenied):
                    self.authorize()
                transaction.set_rollback(True)
        self.grant.delete()
        with self.assertRaises(GatewayDenied):
            self.authorize()

    def test_inactive_or_revoked_principal_and_org_deny(self):
        for model, pk in ((ServicePrincipal, self.principal.pk),
                          (OfficeOrganizationBinding, self.organization.pk)):
            for changes in ({"active": False}, {"revoked_at": timezone.now()}):
                with transaction.atomic():
                    model.objects.filter(pk=pk).update(**changes)
                    with self.assertRaises(GatewayDenied):
                        self.authorize()
                    transaction.set_rollback(True)

    def test_replay_and_receipt_revocation_checked_on_every_call(self):
        key = "a" * 32
        first, replayed = reserve_metadata_receipt(self.identity, key=key, body=self.body)
        self.assertFalse(replayed)
        self.assertEqual(reserve_metadata_receipt(self.identity, key=key, body=self.body), (first, True))
        changed = json.loads(self.body)
        changed["correlation_id"] = str(uuid4())
        with self.assertRaisesMessage(GatewayDenied, "idempotency_conflict"):
            reserve_metadata_receipt(self.identity, key=key, body=json.dumps(changed).encode())
        revoke_grant(self.grant.pk)
        with self.assertRaises(GatewayDenied):
            reserve_metadata_receipt(self.identity, key=key, body=self.body)
        self.assertEqual(IdempotencyReceipt.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 3)

    def test_nonce_reuse_clock_skew_and_store_failure(self):
        nonce = "b" * 32
        reserve_nonce(self.identity, nonce=nonce, timestamp=timezone.now())
        with self.assertRaisesMessage(GatewayDenied, "nonce_reused"):
            reserve_nonce(self.identity, nonce=nonce, timestamp=timezone.now())
        for value, timestamp in (("short", timezone.now()), (nonce, None),
                                 (nonce, timezone.now() - timedelta(seconds=61))):
            with self.assertRaises(GatewayDenied):
                reserve_nonce(self.identity, nonce=value, timestamp=timestamp)
        with patch("apps.ai_gateway.replay.RequestNonce.objects.create", side_effect=OperationalError("secret")):
            with self.assertRaisesMessage(GatewayDenied, "security_unavailable"):
                reserve_nonce(self.identity, nonce="c" * 32, timestamp=timezone.now())
        self.assertEqual(RequestNonce.objects.count(), 1)

    def test_audit_failure_rolls_back_new_receipt_and_revocation(self):
        with patch("apps.ai_gateway.receipts.AuditEvent.objects.create", side_effect=OperationalError("secret")):
            with self.assertRaisesMessage(GatewayDenied, "security_unavailable"):
                reserve_metadata_receipt(self.identity, key="d" * 32, body=self.body)
            with self.assertRaises(GatewayDenied):
                revoke_grant(self.grant.pk)
        self.assertFalse(IdempotencyReceipt.objects.exists())
        self.assertTrue(OperationGrant.objects.get(pk=self.grant.pk).active)

    def test_policy_store_failure_denies(self):
        with patch("apps.ai_gateway.policy.ServicePrincipal.objects.get", side_effect=OperationalError("secret")):
            with self.assertRaisesMessage(GatewayDenied, "security_unavailable"):
                self.authorize()

    def test_database_constraints_and_empty_defaults(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            OperationGrant.objects.create(
                principal=self.principal, organization=self.organization, operation=self.grant.operation,
                version=1, scope_ref=self.principal.pk, expires_at=self.grant.expires_at,
            )
        self.assertFalse(ServicePrincipal(agent_id="micah", environment="synthetic").active)
        self.assertFalse(OfficeOrganizationBinding().active)
        self.assertFalse(OperationGrant().active)


class SchemaTests(SimpleTestCase):
    def test_unknown_duplicate_ambiguous_and_oversized_fields_rejected(self):
        for body in (b'{}', b'[]', b'{"schema_version":1,"schema_version":1}', b'NaN',
                     b'null', b'"text"', b'\xff', b'x' * 1025):
            with self.subTest(body=body[:40]), self.assertRaises(GatewayDenied):
                metadata_envelope(body)
        valid = {"schema_version": 1, "purpose": "gateway_metadata", "correlation_id": str(uuid4())}
        for key, value in (("schema_version", True), ("purpose", "posting"),
                           ("correlation_id", []), ("created_by", "staff")):
            with self.assertRaises(GatewayDenied):
                metadata_envelope(json.dumps({**valid, key: value}).encode())

    def test_canonical_digest_is_order_independent(self):
        value = {"schema_version": 1, "purpose": "gateway_metadata", "correlation_id": str(uuid4())}
        one = metadata_envelope(json.dumps(value).encode())[1]
        two = metadata_envelope(json.dumps(dict(reversed(list(value.items())))).encode())[1]
        self.assertEqual(one, two)

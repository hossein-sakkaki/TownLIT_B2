# apps/ai_gateway/tests/test_mysql.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.ai_gateway.errors import GatewayDenied
from apps.ai_gateway.models import AuditEvent, IdempotencyReceipt, RequestNonce
from apps.ai_gateway.receipts import reserve_metadata_receipt, revoke_grant
from apps.ai_gateway.replay import reserve_nonce

from .test_metadata import fixture


@skipUnless(connection.vendor == "mysql", "requires disposable MySQL transactions")
@override_settings(AI_GATEWAY_ENABLED=True)
class MySQLConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.principal, self.organization, self.grant, self.identity, self.body = (
            fixture()
        )

    def race(self, left, right):
        barrier = Barrier(2)

        def run(action):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return action()
            except GatewayDenied as exc:
                return exc.code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, action) for action in (left, right)]
            return [future.result(timeout=20) for future in futures]

    def test_same_key_serializes_to_one_receipt(self):
        def action():
            return reserve_metadata_receipt(self.identity, key="a" * 32, body=self.body)

        results = self.race(action, action)
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(result[1] for result in results), [False, True])
        self.assertEqual(IdempotencyReceipt.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 2)

    def test_nonce_has_one_winner(self):
        def action():
            return reserve_nonce(
                self.identity, nonce="b" * 32, timestamp=timezone.now()
            )

        results = self.race(action, action)
        self.assertEqual(results.count(None), 1)
        self.assertEqual(results.count("nonce_reused"), 1)
        self.assertEqual(RequestNonce.objects.count(), 1)

    def test_revocation_and_receipt_serialize(self):
        def action():
            return reserve_metadata_receipt(self.identity, key="c" * 32, body=self.body)

        results = self.race(action, lambda: revoke_grant(self.grant.pk))
        self.assertIsNone(results[1])
        self.assertIn(
            results[0] if isinstance(results[0], str) else "allowed_before_revoke",
            {"access_denied", "allowed_before_revoke"},
        )
        with self.assertRaises(GatewayDenied):
            action()
        self.assertLessEqual(IdempotencyReceipt.objects.count(), 1)

    def test_conflicting_payloads_have_one_winner(self):
        changed = json.loads(self.body)
        changed["correlation_id"] = str(uuid4())
        changed_body = json.dumps(changed).encode()
        results = self.race(
            lambda: reserve_metadata_receipt(
                self.identity, key="d" * 32, body=self.body
            ),
            lambda: reserve_metadata_receipt(
                self.identity, key="d" * 32, body=changed_body
            ),
        )
        self.assertEqual(results.count("idempotency_conflict"), 1)
        winner = next(result for result in results if isinstance(result, tuple))
        self.assertFalse(winner[1])
        self.assertEqual(IdempotencyReceipt.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)

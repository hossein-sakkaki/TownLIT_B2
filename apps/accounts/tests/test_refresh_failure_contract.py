# apps/accounts/tests/test_refresh_failure_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-07.
# Last Update by Hossein Sakkaki on 2026-11-07.
#

"""Synthetic refresh faults on real MySQL; no new consumption/retry protocol."""

from datetime import timedelta
from unittest.mock import patch

import rest_framework_simplejwt
from django.contrib.auth import get_user_model
from django.db import (
    IntegrityError,
    InterfaceError,
    OperationalError,
    ProgrammingError,
    connection,
)
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers.session_refresh import _RefreshTokenPreflight
from apps.accounts.services.session_jwt import issue_session_refresh_token
from apps.accounts.services.session_security import (
    get_session_generation,
    increment_session_generation,
)

BOUNDARY = "apps.accounts.serializers.session_refresh."
SENTINEL = "synthetic-private-internal-detail"
UNAVAILABLE = {
    "message": "Session validation temporarily unavailable. Please try again later.",
    "error": {
        "detail": "Session validation temporarily unavailable. Please try again later.",
        "code": "refresh_unavailable",
    },
}
FAILED = {
    "message": "Session validation failed.",
    "error": {"detail": "Session validation failed.", "code": "refresh_failed"},
}


class RefreshFaultAssertions:
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            email="refresh-fault@example.invalid", password="SyntheticPassword42!"
        )
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=True)
        self.user.refresh_from_db()

    def post(self, token):
        return APIClient().post(
            "/api/token/refresh/", {"refresh": str(token)}, format="json"
        )

    def assert_failure(self, response, token, status):
        self.assertEqual(response.status_code, status)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertNotIn(str(token), response.content.decode())
        self.assertNotIn(SENTINEL, response.content.decode())
        if status == 503:
            self.assertEqual(response.json(), UNAVAILABLE)
        elif status == 500:
            self.assertEqual(response.json(), FAILED)

    def assert_state_and_retry(self, token, *, consumed):
        self.assertEqual(get_session_generation(self.user.pk), 0)
        self.assertEqual(
            BlacklistedToken.objects.filter(token__jti=token["jti"]).exists(), consumed
        )
        self.assertTrue(OutstandingToken.objects.filter(jti=token["jti"]).exists())
        retry = self.post(token)
        if consumed:
            self.assert_failure(retry, token, 401)
        else:
            self.assertEqual(retry.status_code, 200)


@override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
class RefreshFailureContractTests(RefreshFaultAssertions, TestCase):
    def test_failure_before_signature_verification_never_issues_credentials(self):
        for error, status in (
            (TimeoutError(SENTINEL), 503),
            (ConnectionError(SENTINEL), 503),
            (RuntimeError(SENTINEL), 500),
        ):
            token = issue_session_refresh_token(self.user)
            with self.subTest(error=type(error).__name__):
                with patch.object(
                    _RefreshTokenPreflight, "get_token_backend", side_effect=error
                ):
                    with patch(BOUNDARY + "_verified_refresh_user_id") as normalize:
                        self.assert_failure(self.post(token), token, status)
                        normalize.assert_not_called()
                self.assert_state_and_retry(token, consumed=False)

    def test_known_invalid_tokens_remain_401_when_blacklist_db_is_unavailable(self):
        malformed = "not-a-jwt"
        token = issue_session_refresh_token(self.user)
        pieces = str(token).split(".")
        token["user_id"] = str(self.user.pk + 1)
        forged = str(token).split(".")
        forged[2] = pieces[2]
        expired = issue_session_refresh_token(self.user)
        expired.set_exp(lifetime=timedelta(seconds=-1))
        missing_jti = issue_session_refresh_token(self.user)
        del missing_jti["jti"]
        bad_id = issue_session_refresh_token(self.user)
        bad_id["user_id"] = "01"
        bad_generation = issue_session_refresh_token(self.user)
        bad_generation["tl_sg"] = True
        for raw in (
            malformed,
            ".".join(forged),
            str(expired),
            str(token.access_token),
            str(missing_jti),
            str(bad_id),
            str(bad_generation),
        ):
            with self.subTest(kind=raw[:8]):
                with patch.object(
                    BlacklistedToken.objects,
                    "filter",
                    side_effect=OperationalError(SENTINEL),
                ) as lookup:
                    self.assert_failure(self.post(raw), raw, 401)
                    lookup.assert_not_called()

    def test_blacklisted_and_revoked_tokens_still_deny_without_rotation(self):
        blacklisted = issue_session_refresh_token(self.user)
        blacklisted.blacklist()
        revoked = issue_session_refresh_token(self.user)
        increment_session_generation(self.user.pk)
        before = OutstandingToken.objects.count()
        for token in (blacklisted, revoked):
            self.assert_failure(self.post(token), token, 401)
        self.assertEqual(OutstandingToken.objects.count(), before)
        self.assertEqual(get_session_generation(self.user.pk), 1)

    def test_unreadable_revocation_state_is_503_never_authorization(self):
        token = issue_session_refresh_token(self.user)
        increment_session_generation(self.user.pk)
        with patch(
            "apps.accounts.services.session_generation_policy.get_session_generation",
            side_effect=InterfaceError(SENTINEL),
        ):
            self.assert_failure(self.post(token), token, 503)
        self.assert_failure(self.post(token), token, 401)
        self.assertEqual(get_session_generation(self.user.pk), 1)
        self.assertFalse(
            BlacklistedToken.objects.filter(token__jti=token["jti"]).exists()
        )

    def test_each_blacklist_read_outage_is_503_without_consumption(self):
        original = BlacklistedToken.objects.filter
        for failing_call in (1, 2):
            token = issue_session_refresh_token(self.user)
            calls = 0

            def lookup(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == failing_call:
                    raise OperationalError(SENTINEL)
                return original(*args, **kwargs)

            with self.subTest(failing_call=failing_call):
                with patch.object(
                    BlacklistedToken.objects, "filter", side_effect=lookup
                ):
                    self.assert_failure(self.post(token), token, 503)
                self.assertEqual(calls, failing_call)
                self.assert_state_and_retry(token, consumed=False)

    def test_parent_user_lookup_outage_matches_profile_and_never_consumes_on_error(
        self,
    ):
        token = issue_session_refresh_token(self.user)
        original = get_user_model().objects.get
        calls = 0

        def lookup(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OperationalError(SENTINEL)
            return original(*args, **kwargs)

        with patch.object(get_user_model().objects, "get", side_effect=lookup):
            response = self.post(token)
        if rest_framework_simplejwt.__version__ == "5.5.1":
            self.assert_failure(response, token, 503)
            self.assertEqual(calls, 2)
            self.assert_state_and_retry(token, consumed=False)
        else:
            # 5.3.1 does not perform the parent's current-user/outstanding lookup.
            self.assertEqual(response.status_code, 200)
            self.assertEqual(calls, 1)
            self.assert_state_and_retry(token, consumed=True)

    def test_account_policy_denials_are_not_retryable_infrastructure_errors(self):
        for outcome, status in (
            (False, 401),
            (AuthenticationFailed(SENTINEL), 401),
            (PermissionDenied(SENTINEL), 403),
            (RuntimeError(SENTINEL), 500),
            (OperationalError(SENTINEL), 503),
        ):
            token = issue_session_refresh_token(self.user)
            kwargs = (
                {"side_effect": outcome}
                if isinstance(outcome, Exception)
                else {"return_value": outcome}
            )
            with self.subTest(outcome=type(outcome).__name__):
                with patch(
                    BOUNDARY + "api_settings.USER_AUTHENTICATION_RULE", **kwargs
                ):
                    self.assert_failure(self.post(token), token, status)
                self.assert_state_and_retry(token, consumed=False)

    def test_unexpected_db_errors_are_redacted_500_not_invalid_or_retryable(self):
        for error in (ProgrammingError, IntegrityError, RuntimeError):
            token = issue_session_refresh_token(self.user)
            with self.subTest(error=error.__name__):
                with patch.object(
                    get_user_model().objects, "get", side_effect=error(SENTINEL)
                ):
                    self.assert_failure(self.post(token), token, 500)
                self.assert_state_and_retry(token, consumed=False)

    def test_parent_blacklist_failure_before_consumption_allows_later_retry(self):
        token = issue_session_refresh_token(self.user)
        with patch.object(
            RefreshToken, "blacklist", side_effect=InterfaceError(SENTINEL)
        ):
            self.assert_failure(self.post(token), token, 503)
        self.assert_state_and_retry(token, consumed=False)

    def test_outstanding_and_blacklist_write_failures_preserve_state(self):
        for manager in (OutstandingToken.objects, BlacklistedToken.objects):
            token = issue_session_refresh_token(self.user)
            with self.subTest(table=manager.model.__name__):
                with patch.object(
                    manager, "get_or_create", side_effect=OperationalError(SENTINEL)
                ):
                    self.assert_failure(self.post(token), token, 503)
                self.assert_state_and_retry(token, consumed=False)

    def test_failure_after_blacklist_consumption_cannot_restore_old_refresh(self):
        token = issue_session_refresh_token(self.user)
        original = RefreshToken.blacklist

        def consume_then_fail(refresh):
            original(refresh)
            raise OperationalError(SENTINEL)

        with patch.object(RefreshToken, "blacklist", consume_then_fail):
            self.assert_failure(self.post(token), token, 503)
        self.assert_state_and_retry(token, consumed=True)

    def test_rotation_failure_after_consumption_returns_no_credentials(self):
        token = issue_session_refresh_token(self.user)
        with patch.object(RefreshToken, "set_jti", side_effect=TimeoutError(SENTINEL)):
            self.assert_failure(self.post(token), token, 503)
        self.assert_state_and_retry(token, consumed=True)

    def test_new_outstanding_creation_failure_is_profile_specific_and_fail_closed(self):
        token = issue_session_refresh_token(self.user)
        original = OutstandingToken.objects.get_or_create
        attempted_jtis = []

        def create_outstanding(*args, **kwargs):
            attempted_jtis.append(kwargs["jti"])
            if kwargs["jti"] != token["jti"]:
                raise OperationalError(SENTINEL)
            return original(*args, **kwargs)

        with patch.object(
            OutstandingToken.objects, "get_or_create", side_effect=create_outstanding
        ):
            response = self.post(token)
        if rest_framework_simplejwt.__version__ == "5.5.1":
            self.assert_failure(response, token, 503)
            self.assertEqual(len(attempted_jtis), 2)
            self.assertNotEqual(attempted_jtis[1], token["jti"])
            self.assertFalse(
                OutstandingToken.objects.filter(jti=attempted_jtis[1]).exists()
            )
        else:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(attempted_jtis, [token["jti"]])
        self.assertEqual(attempted_jtis[0], token["jti"])
        self.assert_state_and_retry(token, consumed=True)

    def test_lost_success_response_does_not_make_consumed_refresh_retryable(self):
        token = issue_session_refresh_token(self.user)
        server_response = self.post(token)
        self.assertEqual(server_response.status_code, 200)
        # Model the client retaining only the submitted token after losing the
        # successful response. The server cannot detect/remap a lost HTTP ack.
        self.assert_state_and_retry(token, consumed=True)
        # The new credential exists, but is unavailable to that client. This
        # assertion is server-side evidence only, not transparent recovery.
        self.assertEqual(self.post(server_response.data["refresh"]).status_code, 200)


@override_settings(AUTH_SESSION_GENERATION_ENFORCE=False)
class RefreshConnectionOutageTests(RefreshFaultAssertions, TransactionTestCase):
    def setUp(self):
        # Autocommit executes user post-save/on-commit hooks in this case.
        # Bind the existing isolated memory broker, never the default AMQP app.
        from townlit_b.celery import app

        app.set_current()
        app.set_default()
        self.assertEqual(app.conf.broker_url, "memory://")
        self.assertFalse(app.conf.task_always_eager)
        super().setUp()

    def test_real_connection_reopen_failure_is_503_and_retry_does_not_revoke(self):
        self.assertEqual(connection.vendor, "mysql")
        token = issue_session_refresh_token(self.user)
        connection.close()
        with patch.object(
            connection,
            "get_new_connection",
            side_effect=OperationalError(2003, SENTINEL),
        ):
            self.assert_failure(self.post(token), token, 503)
        self.assert_state_and_retry(token, consumed=False)

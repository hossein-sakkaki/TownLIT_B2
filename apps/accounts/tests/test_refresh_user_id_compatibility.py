# apps/accounts/tests/test_refresh_user_id_compatibility.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-07.
# Last Update by Hossein Sakkaki on 2026-11-07.
#

"""Signed refresh compatibility; shared identity/session validators stay strict."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.serializers.session_refresh import _verified_refresh_user_id
from apps.accounts.services.session_generation_policy import session_generation_matches
from apps.accounts.services.session_jwt import issue_session_refresh_token
from apps.accounts.services.session_security import increment_session_generation
from apps.core.websocket.access_auth import (
    validate_access_token_for_websocket,
    validate_legacy_websocket_session_access,
)

INVALID_IDS = (
    None,
    True,
    False,
    0,
    -1,
    1.0,
    1.5,
    [],
    {},
    "",
    "0",
    "00",
    "01",
    "+1",
    "-1",
    " 1",
    "1 ",
    "1\n",
    "1\x00",
    "1.0",
    "1e0",
    "0x1",
    "１",
    "١",
    "²",
    "1١",
    "1_0",
    2**63,
    str(2**63),
    10**100,
    "9" * 10000,
)


class VerifiedRefreshUserIDTests(SimpleTestCase):
    def test_accepts_only_positive_bigautofield_integer_or_canonical_ascii_string(self):
        self.assertEqual(get_user_model()._meta.pk.get_internal_type(), "BigAutoField")
        for value in (1, 42, 2**63 - 1):
            for claim in (value, str(value)):
                with self.subTest(claim=claim):
                    result = _verified_refresh_user_id(claim)
                    self.assertIs(type(result), int)
                    self.assertEqual(result, value)

    def test_rejects_ambiguous_malformed_unicode_and_overflow_claims(self):
        for claim in INVALID_IDS:
            with self.subTest(kind=type(claim).__name__, sample=str(claim)[:30]):
                with self.assertRaises(InvalidToken):
                    _verified_refresh_user_id(claim)


@override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
class RefreshUserIDCompatibilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="refresh-compat@example.com", password="ExistingPassword42!"
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])
        self.client = APIClient()

    def _token(self, claim_type=str, legacy=False):
        token = (
            RefreshToken.for_user(self.user)
            if legacy
            else issue_session_refresh_token(self.user)
        )
        token["user_id"] = claim_type(self.user.pk)
        return token

    def _refresh(self, token):
        return self.client.post(
            "/api/token/refresh/", {"refresh": str(token)}, format="json"
        )

    def _assert_denied(self, response):
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_legacy_integer_claim_rotates_without_changing_wire_type(self):
        self._assert_rotation(int)

    def test_canonical_string_claim_rotates_without_changing_wire_type(self):
        self._assert_rotation(str)

    def _assert_rotation(self, claim_type):
        increment_session_generation(self.user.pk)
        token = self._token(claim_type)
        response = self._refresh(token)
        self.assertEqual(response.status_code, 200)
        rotated = RefreshToken(response.data["refresh"])
        access = AccessToken(response.data["access"])
        self.assertNotEqual(rotated["jti"], token["jti"])
        for result in (rotated, access):
            self.assertIs(type(result["user_id"]), claim_type)
            self.assertEqual(result["user_id"], claim_type(self.user.pk))
            self.assertEqual(result["tl_sg"], 1)
        self.assertTrue(
            BlacklistedToken.objects.filter(token__jti=token["jti"]).exists()
        )
        self._assert_denied(self._refresh(token))
        self.assertEqual(self._refresh(rotated).status_code, 200)

    def test_revoked_refresh_rejected_for_both_claim_types(self):
        tokens = [self._token(kind) for kind in (int, str)]
        increment_session_generation(self.user.pk)
        for token in tokens:
            with self.subTest(claim_type=type(token["user_id"])):
                self._assert_denied(self._refresh(token))

    def test_legacy_generation_zero_accepted_only_before_revocation(self):
        for kind in (int, str):
            with self.subTest(claim_type=kind):
                self.assertEqual(
                    self._refresh(self._token(kind, legacy=True)).status_code, 200
                )
        tokens = [self._token(kind, legacy=True) for kind in (int, str)]
        increment_session_generation(self.user.pk)
        for token in tokens:
            self._assert_denied(self._refresh(token))

    def test_signed_invalid_ids_rejected_before_account_or_generation_lookup(self):
        for claim in INVALID_IDS:
            token = self._token()
            token["user_id"] = claim
            with self.subTest(kind=type(claim).__name__, sample=str(claim)[:30]):
                with patch(
                    "apps.accounts.serializers.session_refresh.get_user_model"
                ) as user_model:
                    with patch(
                        "apps.accounts.serializers.session_refresh.session_generation_matches"
                    ) as matches:
                        self._assert_denied(self._refresh(token))
                        user_model.assert_not_called()
                        matches.assert_not_called()

    def test_missing_id_claim_is_denied(self):
        token = self._token()
        del token["user_id"]
        self._assert_denied(self._refresh(token))

    def test_tampered_or_malformed_token_never_reaches_normalization(self):
        token = self._token()
        # Alter signed payload while retaining the original signature.
        original = str(token).split(".")
        token["user_id"] = str(self.user.pk + 1)
        forged = str(token).split(".")
        forged[2] = original[2]
        for raw in ("not-a-jwt", ".".join(forged), str(token.access_token)):
            with self.subTest(raw_kind=raw[:10]):
                with patch(
                    "apps.accounts.serializers.session_refresh._verified_refresh_user_id"
                ) as normalize:
                    self._assert_denied(self._refresh(raw))
                    normalize.assert_not_called()

    def test_expired_and_blacklisted_tokens_are_denied(self):
        from datetime import timedelta

        token = self._token()
        token.set_exp(lifetime=timedelta(seconds=-1))
        self._assert_denied(self._refresh(token))
        token = self._token()
        token.blacklist()
        self._assert_denied(self._refresh(token))

    def test_inactive_denial_and_existing_domain_restrictions_are_preserved(self):
        for flag, value in (
            ("is_active", False),
            ("is_deleted", True),
            ("is_suspended", True),
        ):
            for kind in (int, str):
                token = self._token(kind)
                get_user_model().objects.filter(pk=self.user.pk).update(**{flag: value})
                with self.subTest(flag=flag, claim_type=kind):
                    if flag == "is_active":
                        self._assert_denied(self._refresh(token))
                    else:
                        # Canonical login issues limited reactivation tokens;
                        # suspended accounts retain an explicit logout exception.
                        # Preserve these domain gates instead of inventing a
                        # blanket refresh-level account policy.
                        from types import SimpleNamespace

                        from apps.accounts.views.auth_views import AuthViewSet
                        from apps.core.api_exceptions import (
                            DeletedAccount,
                            SuspendedAccount,
                        )
                        from apps.core.permissions import DenyIfDeletedOrSuspended

                        self.assertEqual(self._refresh(token).status_code, 200)
                        current = get_user_model().objects.get(pk=self.user.pk)
                        request = SimpleNamespace(user=current)
                        view = AuthViewSet()
                        view.action = "protected_action"
                        expected = (
                            DeletedAccount if flag == "is_deleted" else SuspendedAccount
                        )
                        with self.assertRaises(expected):
                            DenyIfDeletedOrSuspended().has_permission(request, view)
                        view.action = (
                            "confirm_reactivate_account"
                            if flag == "is_deleted"
                            else "logout"
                        )
                        self.assertTrue(
                            DenyIfDeletedOrSuspended().has_permission(request, view)
                        )
                    self.assertIsNone(
                        validate_access_token_for_websocket(str(token.access_token))
                    )
                    self.assertFalse(
                        validate_legacy_websocket_session_access(self.user.pk, 0)
                    )
                get_user_model().objects.filter(pk=self.user.pk).update(
                    **{flag: not value}
                )

    def test_physically_deleted_account_is_denied(self):
        tokens = [self._token(kind) for kind in (int, str)]
        self.user.delete()
        for token in tokens:
            self._assert_denied(self._refresh(token))

    def test_generation_database_failure_denies_without_rotation(self):
        token = self._token()
        with patch(
            "apps.accounts.services.session_generation_policy.get_session_generation",
            side_effect=OperationalError("synthetic outage"),
        ):
            self._assert_denied(self._refresh(token))
        self.assertFalse(
            BlacklistedToken.objects.filter(token__jti=token["jti"]).exists()
        )
        self.assertEqual(self._refresh(token).status_code, 200)

    def test_account_lookup_failure_denies_without_rotation(self):
        token = self._token()
        with patch.object(
            get_user_model().objects,
            "get",
            side_effect=OperationalError("synthetic outage"),
        ):
            self._assert_denied(self._refresh(token))
        self.assertFalse(
            BlacklistedToken.objects.filter(token__jti=token["jti"]).exists()
        )

    def test_blacklist_database_failure_denies_before_normalization(self):
        token = self._token()
        with patch.object(
            BlacklistedToken.objects,
            "filter",
            side_effect=OperationalError("synthetic outage"),
        ):
            with patch(
                "apps.accounts.serializers.session_refresh._verified_refresh_user_id"
            ) as normalize:
                self._assert_denied(self._refresh(token))
                normalize.assert_not_called()

    def test_outstanding_database_failure_denies_rotation(self):
        token = self._token()
        with patch.object(
            OutstandingToken.objects,
            "get_or_create",
            side_effect=OperationalError("synthetic outage"),
        ):
            self._assert_denied(self._refresh(token))

    def test_malformed_generation_claims_are_still_denied(self):
        for claim in ("0", True, -1, 0.0):
            token = self._token()
            token["tl_sg"] = claim
            self._assert_denied(self._refresh(token))

    def test_websocket_generation_outage_still_denies(self):
        token = self._token().access_token
        with patch(
            "apps.accounts.services.session_generation_policy.get_session_generation",
            side_effect=OperationalError("synthetic outage"),
        ):
            self.assertIsNone(validate_access_token_for_websocket(str(token)))
            self.assertFalse(validate_legacy_websocket_session_access(self.user.pk, 0))

    def test_current_user_authentication_rule_is_preserved(self):
        token = self._token()
        with patch(
            "apps.accounts.serializers.session_refresh.api_settings.USER_AUTHENTICATION_RULE",
            return_value=False,
        ):
            self._assert_denied(self._refresh(token))

    def test_outstanding_rotation_follows_upstream_profile(self):
        import rest_framework_simplejwt

        token = self._token()
        response = self._refresh(token)
        self.assertEqual(response.status_code, 200)
        rotated = RefreshToken(response.data["refresh"])
        self.assertEqual(
            OutstandingToken.objects.filter(jti=rotated["jti"]).exists(),
            rest_framework_simplejwt.__version__ == "5.5.1",
        )
        if rest_framework_simplejwt.__version__ == "5.5.1":
            row = OutstandingToken.objects.get(jti=rotated["jti"])
            self.assertEqual(row.user_id, self.user.pk)
            self.assertIsNotNone(row.created_at)
        # 5.3.1 records a rotated token when it is subsequently blacklisted.
        rotated.blacklist()
        self.assertTrue(OutstandingToken.objects.filter(jti=rotated["jti"]).exists())
        with self.assertRaises(TokenError):
            RefreshToken(str(rotated))

    def test_shared_generation_validator_and_legacy_session_ids_remain_strict(self):
        self.assertFalse(session_generation_matches(str(self.user.pk), 0))
        self.assertFalse(session_generation_matches(True, 0))
        self.assertFalse(validate_legacy_websocket_session_access(str(self.user.pk), 0))

    def test_string_access_claim_still_rechecks_generation_for_websocket(self):
        token = self._token().access_token
        self.assertEqual(
            validate_access_token_for_websocket(str(token)).pk, self.user.pk
        )
        increment_session_generation(self.user.pk)
        self.assertIsNone(validate_access_token_for_websocket(str(token)))

    def test_restricted_owner_keeps_limited_refresh_but_websocket_denies(self):
        from apps.profiles.models.member import Member

        self.user.is_member = True
        self.user.save(update_fields=["is_member"])
        Member.objects.create(
            user=self.user,
            is_active=True,
            is_hidden_by_confidants=True,
            denomination_branch="other",
        )
        for kind in (int, str):
            token = self._token(kind)
            self.assertEqual(self._refresh(token).status_code, 200)
            self.assertIsNone(
                validate_access_token_for_websocket(str(token.access_token))
            )
            self.assertFalse(validate_legacy_websocket_session_access(self.user.pk, 0))

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=False)
    def test_disabled_generation_enforcement_still_requires_valid_current_account(self):
        token = self._token()
        increment_session_generation(self.user.pk)
        self.assertEqual(self._refresh(token).status_code, 200)
        token = self._token()
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        self._assert_denied(self._refresh(token))

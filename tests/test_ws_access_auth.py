# tests/test_ws_access_auth.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-23.
# Last Update by Hossein Sakkaki on 2026-11-02.

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.core.websocket import access_auth


class WebSocketAccessAuthTests(unittest.TestCase):

    def setUp(self):
        self.user = SimpleNamespace(
            id=1,
            is_authenticated=True,
            is_active=True,
            is_deleted=False,
        )

        token = AccessToken()
        token["user_id"] = self.user.id

        self.access_token = str(token)

    def validate(self, user=None, restricted=False):
        with patch.object(
            JWTAuthentication,
            "get_user",
            return_value=self.user if user is None else user,
        ):
            with patch.object(
                access_auth,
                "is_restricted_owner_user",
                return_value=restricted,
            ):
                return access_auth.validate_access_token_for_websocket(
                    self.access_token
                )

    def test_valid_access_token(self):
        self.assertIs(self.validate(), self.user)

    def test_refresh_token_rejected(self):
        refresh = RefreshToken()
        refresh["user_id"] = self.user.id

        with patch.object(JWTAuthentication, "get_user") as get_user:
            result = access_auth.validate_access_token_for_websocket(
                str(refresh)
            )

        self.assertIsNone(result)
        get_user.assert_not_called()

    def test_invalid_token_rejected(self):
        self.assertIsNone(
            access_auth.validate_access_token_for_websocket(
                "invalid-token"
            )
        )

    def test_inactive_user_rejected(self):
        self.user.is_active = False
        self.assertIsNone(self.validate())

    def test_suspended_user_rejected(self):
        self.user.is_suspended = True
        self.assertIsNone(self.validate())

    def test_soft_deleted_user_rejected(self):
        self.user.is_deleted = True
        self.assertIsNone(self.validate())

    def test_restricted_owner_rejected(self):
        self.assertIsNone(self.validate(restricted=True))

    def test_account_gate_failure_is_closed(self):
        with patch.object(
            JWTAuthentication,
            "get_user",
            return_value=self.user,
        ):
            with patch.object(
                access_auth,
                "is_restricted_owner_user",
                side_effect=RuntimeError("Database unavailable"),
            ):
                result = (
                    access_auth.validate_access_token_for_websocket(
                        self.access_token
                    )
                )

        self.assertIsNone(result)

    def test_oversized_token_rejected(self):
        self.assertIsNone(
            access_auth.validate_access_token_for_websocket(
                "a" * 9000
            )
        )


class WebSocketSessionGateTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(
            id=11,
            is_active=True,
            is_deleted=False,
            is_suspended=False,
            is_authenticated=True,
            is_member=False,
        )

    def check(self, *, active_device=True, restricted=False):
        with patch.object(access_auth.User.objects, "get", return_value=self.user):
            with patch.object(
                access_auth,
                "is_restricted_owner_user",
                return_value=restricted,
            ):
                with patch.object(access_auth.UserDeviceKey.objects, "filter") as filt:
                    filt.return_value.exists.return_value = active_device
                    result = access_auth.validate_websocket_session_access(
                        11,
                        "valid-device",
                    )
                    return result, filt

    def test_active_registered_device_allowed(self):
        result, filt = self.check()
        self.assertTrue(result)
        filt.assert_called_once_with(
            user_id=11,
            device_id="valid-device",
            is_active=True,
        )

    def test_unregistered_or_revoked_device_denied(self):
        result, _ = self.check(active_device=False)
        self.assertFalse(result)

    def test_restricted_account_denied(self):
        result, filt = self.check(restricted=True)
        self.assertFalse(result)
        filt.assert_not_called()

    def test_suspended_account_denied(self):
        self.user.is_suspended = True
        result, filt = self.check()
        self.assertFalse(result)
        filt.assert_not_called()

    def test_missing_device_denied(self):
        self.assertFalse(access_auth.validate_websocket_session_access(11, ""))


if __name__ == "__main__":
    unittest.main()

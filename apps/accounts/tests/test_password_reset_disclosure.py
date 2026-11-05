# apps/accounts/tests/test_password_reset_disclosure.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-04.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.views.auth_views import AuthViewSet
from apps.profiles.views.member import MemberViewSet


class PasswordResetDisclosureTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            email="account-holder@example.com",
            username="p0_account_holder",
            password="ExistingPassword42!",
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

    def _forgot(self, email):
        request = self.factory.post(
            "/api/v1/accounts/auth/forget-password/",
            {"email": email},
            format="json",
        )
        with patch.object(AuthViewSet, "get_throttles", return_value=[]):
            return AuthViewSet.as_view({"post": "forget_password"})(request)

    def _reset(self, token, new_password):
        request = self.factory.post(
            f"/api/v1/accounts/auth/reset-password/{token}/",
            {"new_password": new_password},
            format="json",
        )
        with patch.object(AuthViewSet, "get_throttles", return_value=[]):
            return AuthViewSet.as_view({"post": "reset_password"})(
                request,
                reset_token=token,
            )

    @patch("apps.accounts.views.auth_views.send_custom_email", return_value=True)
    def test_registered_and_unknown_accounts_return_same_public_response(self, send_email):
        registered = self._forgot(self.user.email)
        unknown = self._forgot("unknown@example.com")

        self.assertEqual(registered.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(registered.data, unknown.data)
        self.assertEqual(set(registered.data), {"message"})
        self.assertNotIn("reset_token", registered.data)
        self.assertNotIn("reset_link", registered.data)
        send_email.assert_called_once()
        self.user.refresh_from_db()
        self.assertTrue(self.user.reset_token)
        self.assertIsNotNone(self.user.reset_token_expiration)
        link = send_email.call_args.kwargs["context"]["reset_link"]
        bearer = link.rstrip("/").split("/")[-1]
        self.assertTrue(bearer)
        self.assertNotIn("reset_token", registered.data)


    @override_settings(PASSWORD_RESET_FRONTEND_URL="https://dev.townlit.com")
    @patch("apps.accounts.views.auth_views.send_custom_email", return_value=True)
    def test_reset_email_uses_web_frontend_not_api_host(self, send_email):
        response = self._forgot(self.user.email)

        self.assertEqual(response.status_code, 200)
        link = send_email.call_args.kwargs["context"]["reset_link"]
        self.assertTrue(link.startswith("https://dev.townlit.com/reset-password/"))
        self.assertTrue(link.endswith("/"))
        self.assertNotIn("api.dev.townlit.com", link)

    @patch("apps.accounts.views.auth_views.send_custom_email", return_value=False)
    def test_mail_delivery_failure_does_not_disclose_account_existence(self, send_email):
        failed_delivery = self._forgot(self.user.email)
        unknown = self._forgot("unknown@example.com")

        self.assertEqual(failed_delivery.status_code, 200)
        self.assertEqual(failed_delivery.data, unknown.data)
        self.assertNotIn("reset_token", failed_delivery.data)
        send_email.assert_called_once()

    @patch("apps.accounts.views.auth_views.send_custom_email", side_effect=RuntimeError("SMTP service unavailable"))
    def test_mail_transport_exception_does_not_disclose_account_existence(self, send_email):
        registered = self._forgot(self.user.email)
        unknown = self._forgot("unknown@example.com")

        self.assertEqual(registered.status_code, 200)
        self.assertEqual(registered.data, unknown.data)
        send_email.assert_called_once()

    @patch("apps.accounts.views.auth_views.send_custom_email")
    def test_invalid_email_does_not_issue_token_or_send_email(self, send_email):
        response = self._forgot("not-an-email")

        self.assertEqual(response.status_code, 400)
        send_email.assert_not_called()
        self.user.refresh_from_db()
        self.assertIsNone(self.user.reset_token)

    @patch("apps.accounts.views.auth_views.send_custom_email", return_value=True)
    def test_email_link_remains_valid_and_token_is_consumed_once(self, send_email):
        self.assertEqual(self._forgot(self.user.email).status_code, 200)
        self.user.refresh_from_db()
        link = send_email.call_args.kwargs["context"]["reset_link"]
        token = link.rstrip("/").split("/")[-1]

        response = self._reset(token, "ReplacementPassword42!")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ReplacementPassword42!"))
        self.assertIsNone(self.user.reset_token)
        self.assertIsNone(self.user.reset_token_expiration)
        self.assertEqual(self._reset(token, "AnotherPassword42!").status_code, 404)


class PhoneVerificationLogSafetyTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            email="phone-holder@example.com",
            username="p0_phone_holder",
            password="ExistingPassword42!",
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

    @patch("apps.profiles.views.member.validate_phone_number")
    @patch("apps.profiles.views.member.create_active_code", return_value="54321")
    @patch("apps.profiles.views.member.send_sms", return_value={"success": True, "message_id": "test-message", "error": None})
    def test_phone_verification_code_is_not_printed_or_logged(self, send_sms, create_code, validate_phone):
        request = self.factory.post(
            "/api/v1/profiles/member/request-phone-verification/",
            {"phone_number": "+16045550123"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        output = StringIO()

        with redirect_stdout(output), self.assertLogs("apps.profiles.views.member", level="INFO") as logs:
            response = MemberViewSet.as_view({"post": "request_phone_verification"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("54321", response.data["message"])
        self.assertNotIn("54321", output.getvalue())
        self.assertNotIn("54321", "\n".join(logs.output))
        self.assertNotIn("+16045550123", "\n".join(logs.output))
        self.assertIn("54321", send_sms.call_args.kwargs["message"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.mobile_verification_code)

# apps/translations/tests/test_profile_visibility.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-09.
# Last Update by Hossein Sakkaki on 2026-11-09.

"""Regression checks for member story translation access and response contracts."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.response import Response

from apps.translations.views.member_profile import MemberProfileTranslationViewSet


POLICY = "apps.translations.views.member_profile.BoundaryPolicy.has_boundary_between"
VISITOR_GATE = (
    "apps.translations.views.member_profile."
    "VisitorProfileViewSet._profile_content_gate_response"
)


class ProfileTranslationVisibilityTests(SimpleTestCase):
    def setUp(self):
        self.owner = SimpleNamespace(pk=9, id=9)
        self.profile = SimpleNamespace(pk=14, user=self.owner)
        self.viewer = SimpleNamespace(
            pk=10,
            id=10,
            is_authenticated=True,
        )
        self.request = SimpleNamespace(user=self.viewer)
        self.view = MemberProfileTranslationViewSet()

    def test_private_profile_is_denied(self):
        with (
            patch(POLICY, return_value=False),
            patch(VISITOR_GATE, return_value=Response({"blocked": True})),
        ):
            result = self.view._visibility_denial(
                profile=self.profile, request=self.request
            )
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(result.data["code"], "profile_unavailable")

    def test_allowed_profile_uses_canonical_policy(self):
        with (
            patch(POLICY, return_value=False) as boundary,
            patch(VISITOR_GATE, return_value=None) as gate,
        ):
            result = self.view._visibility_denial(
                profile=self.profile, request=self.request
            )
        self.assertIsNone(result)
        boundary.assert_called_once_with(self.viewer, self.owner)
        gate.assert_called_once_with(
            request=self.request,
            profile=self.profile,
            user=self.owner,
            profile_type="member",
        )

    def test_boundary_infrastructure_failure_denies(self):
        with (
            patch(POLICY, side_effect=RuntimeError("offline")),
            patch(VISITOR_GATE) as gate,
        ):
            result = self.view._visibility_denial(
                profile=self.profile, request=self.request
            )
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)
        gate.assert_not_called()

    def test_explicit_boundary_denies_before_profile_policy(self):
        with (
            patch(POLICY, return_value=True),
            patch(VISITOR_GATE) as gate,
        ):
            result = self.view._visibility_denial(
                profile=self.profile, request=self.request
            )
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)
        gate.assert_not_called()

    def test_visitor_gate_failure_denies(self):
        with (
            patch(POLICY, return_value=False),
            patch(VISITOR_GATE, side_effect=RuntimeError("policy offline")),
        ):
            result = self.view._visibility_denial(
                profile=self.profile, request=self.request
            )
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_still_passes_through_profile_gate(self):
        self.request.user = SimpleNamespace(
            pk=9,
            id=9,
            is_authenticated=True,
        )
        with (
            patch(POLICY) as boundary,
            patch(VISITOR_GATE, return_value=None) as gate,
        ):
            result = self.view._visibility_denial(
                profile=self.profile, request=self.request
            )
        self.assertIsNone(result)
        boundary.assert_not_called()
        gate.assert_called_once()

    def test_private_member_profile_is_denied_by_real_visitor_gate(self):
        self.profile.is_privacy = True
        self.profile.is_hidden_by_confidants = False
        self.owner.is_deleted = False
        self.owner.is_suspended = False
        self.owner.is_account_paused = False
        with (
            patch(POLICY, return_value=False),
            patch(
                "apps.profiles.views.visitor_profile."
                "VisitorProfileViewSet._is_friend",
                return_value=False,
            ),
        ):
            result = self.view._visibility_denial(
                profile=self.profile, request=self.request
            )
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)


class ProfileTranslationLanguageContractTests(SimpleTestCase):
    def setUp(self):
        self.view = MemberProfileTranslationViewSet()
        self.profile = SimpleNamespace(
            pk=14, biography="Hello", vision="A better world"
        )
        self.user = SimpleNamespace(
            pk=10, is_authenticated=True, primary_language="tr"
        )
        self.request = SimpleNamespace(
            user=self.user, data={"target_language": "tr"}
        )

    def test_biography_exposes_detected_source_language(self):
        translated = {
            "text": "Merhaba",
            "target_language": "tr",
            "source_language": "en",
            "cached": True,
        }
        with patch(
            "apps.translations.views.member_profile.translate_cached",
            return_value=translated,
        ) as translate:
            response = self.view._translate_field(
                request=self.request,
                profile=self.profile,
                field_name="biography",
                empty_message="Biography is empty.",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source_language"], "en")
        self.assertEqual(response.data["target_language"], "tr")
        translate.assert_called_once_with(
            obj=self.profile,
            field_name="biography",
            user=self.user,
            target_language="tr",
        )

    def test_vision_same_language_is_distinguishable(self):
        translated = {
            "text": "Merhaba",
            "target_language": "tr",
            "source_language": "tr",
            "cached": True,
        }
        with patch(
            "apps.translations.views.member_profile.translate_cached",
            return_value=translated,
        ):
            response = self.view._translate_field(
                request=self.request,
                profile=self.profile,
                field_name="vision",
                empty_message="Vision is empty.",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source_language"], "tr")

    def test_missing_source_language_remains_backward_compatible(self):
        translated = {
            "text": "Merhaba",
            "target_language": "tr",
            "cached": True,
        }
        with patch(
            "apps.translations.views.member_profile.translate_cached",
            return_value=translated,
        ):
            response = self.view._translate_field(
                request=self.request,
                profile=self.profile,
                field_name="biography",
                empty_message="Biography is empty.",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["source_language"])

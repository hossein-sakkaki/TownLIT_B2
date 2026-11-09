# apps/core/square/tests/test_localized_projection.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-09.
# Last Update by Hossein Sakkaki on 2026-11-09.

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.square.projections.base import SquareProjection


class ExampleSquareProjection(SquareProjection):
    kind = "moment"

    def get_preview(self):
        return {"type": "image", "image_url": "https://example.invalid/1.jpg"}

    def get_meta(self):
        return {"excerpt": self.obj.caption[:160]}

    def get_owner_payload(self):
        return {"owner_user_id": 2, "owner_username": "author"}


class SquareCachedLocalizationTests(SimpleTestCase):
    def setUp(self):
        self.obj = SimpleNamespace(
            id=7, pk=7, caption="Hello from TownLIT",
            _meta=SimpleNamespace(label_lower="posts.moment"),
        )
        self.viewer = SimpleNamespace(id=3, is_authenticated=True)

    @patch.object(ExampleSquareProjection, "get_peace_payload")
    @patch("apps.core.square.projections.base.cached_automatic_fields")
    def test_ready_translation_does_not_overwrite_original(self, cached, peace):
        peace.return_value = {"has_boundary_between": False, "direct_interaction_available": True}
        cached.return_value = {
            "target_language": "fa", "fields": {"caption": {
                "original": self.obj.caption,
                "translated": "درود از تاونلیت", "status": "ready",
            }},
        }
        payload = ExampleSquareProjection(self.obj, viewer=self.viewer).serialize()
        self.assertEqual(payload["meta"]["excerpt"], self.obj.caption)
        self.assertEqual(payload["meta"]["localized_excerpt"], "درود از تاونلیت")

    @patch.object(ExampleSquareProjection, "get_peace_payload")
    @patch("apps.core.square.projections.base.cached_automatic_fields")
    def test_stale_or_missing_translation_is_not_sent(self, cached, peace):
        peace.return_value = {"has_boundary_between": False, "direct_interaction_available": True}
        cached.return_value = {
            "fields": {"caption": {"original": "edited source", "translated": "bad", "status": "ready"}},
        }
        payload = ExampleSquareProjection(self.obj, viewer=self.viewer).serialize()
        self.assertNotIn("localized_excerpt", payload["meta"])

    @patch.object(ExampleSquareProjection, "get_peace_payload")
    @patch("apps.core.square.projections.base.cached_automatic_fields")
    def test_guest_never_reads_personalized_cache(self, cached, peace):
        peace.return_value = {"has_boundary_between": False, "direct_interaction_available": True}
        payload = ExampleSquareProjection(self.obj, viewer=SimpleNamespace(is_authenticated=False)).serialize()
        self.assertNotIn("localized_excerpt", payload["meta"])
        cached.assert_not_called()

    @patch.object(ExampleSquareProjection, "get_peace_payload")
    @patch("apps.core.square.projections.base.cached_automatic_fields", side_effect=RuntimeError("cache offline"))
    def test_cache_error_preserves_authorized_original(self, cached, peace):
        peace.return_value = {"has_boundary_between": False, "direct_interaction_available": True}
        payload = ExampleSquareProjection(self.obj, viewer=self.viewer).serialize()
        self.assertEqual(payload["meta"]["excerpt"], self.obj.caption)
        self.assertNotIn("localized_excerpt", payload["meta"])

    @patch("apps.core.square.projections.base.BoundaryPolicy.is_in_stillness", side_effect=RuntimeError("policy offline"))
    def test_boundary_failure_hides_item(self, check):
        projection = ExampleSquareProjection(self.obj, viewer=self.viewer)
        projection.get_owner_user = lambda: SimpleNamespace(id=2)
        self.assertIsNone(projection.serialize())

    @patch.object(ExampleSquareProjection, "get_peace_payload")
    @patch("apps.core.square.projections.base.dispatch_missing_automatic_fields")
    @patch("apps.core.square.projections.base.cached_automatic_fields")
    def test_cache_miss_triggers_background_generation_without_client_click(self, cached, dispatch, peace):
        peace.return_value = {"has_boundary_between": False, "direct_interaction_available": True}
        cached.return_value = {
            "target_language": "tr",
            "fields": {"caption": {"original": self.obj.caption, "status": "missing"}},
        }
        dispatch.return_value = 1
        payload = ExampleSquareProjection(self.obj, viewer=self.viewer).serialize()
        self.assertNotIn("localized_excerpt", payload["meta"])
        dispatch.assert_called_once_with(
            obj=self.obj, presentation=cached.return_value, viewer=self.viewer, remaining=2,
        )

    @patch.object(ExampleSquareProjection, "get_peace_payload")
    @patch("apps.core.square.projections.base.dispatch_missing_automatic_fields")
    def test_boundary_block_never_queues_translation(self, dispatch, peace):
        peace.return_value = {"has_boundary_between": True, "direct_interaction_available": False}
        self.assertIsNone(ExampleSquareProjection(self.obj, viewer=self.viewer).serialize())
        dispatch.assert_not_called()

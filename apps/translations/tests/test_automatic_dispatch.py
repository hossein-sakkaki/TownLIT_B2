# apps/translations/tests/test_automatic_dispatch.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-09.
# Last Update by Hossein Sakkaki on 2026-11-09.

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.cache.backends.locmem import LocMemCache
from django.test import SimpleTestCase, override_settings

from apps.posts.models.moment import Moment
from apps.translations.services.automatic_dispatch import (
    automatic_job_key,
    dispatch_missing_automatic_fields,
)
from apps.translations.services.hashing import hash_text
from apps.translations.tasks import generate_automatic_translation_task


class AutomaticTranslationDispatchTests(SimpleTestCase):
    def setUp(self):
        self.cache = LocMemCache("automatic-dispatch-unit", {})
        self.cache.clear()
        self.obj = SimpleNamespace(
            pk=51,
            _meta=SimpleNamespace(
                app_label="posts",
                model_name="moment",
                label_lower="posts.moment",
            ),
        )
        self.viewer = SimpleNamespace(pk=18, is_authenticated=True, primary_language="fa")
        self.presentation = {
            "target_language": "fa",
            "fields": {
                "caption": {
                    "original": "Hello world",
                    "translated": None,
                    "source_language": None,
                    "status": "missing",
                },
            },
        }

    def _enqueue(self):
        return dispatch_missing_automatic_fields(
            obj=self.obj,
            presentation=self.presentation,
            viewer=self.viewer,
            remaining=3,
        )

    @override_settings(TRANSLATIONS_AUTOMATIC_ENABLED=False)
    def test_disabled_mode_does_not_touch_queue(self):
        with patch("apps.translations.tasks.generate_automatic_translation_task.apply_async") as publish:
            self.assertEqual(self._enqueue(), 0)
        publish.assert_not_called()

    @override_settings(TRANSLATIONS_AUTOMATIC_ENABLED=True)
    def test_queues_once_without_sending_source_text(self):
        with (
            patch("apps.translations.services.automatic_dispatch._dispatch_cache", return_value=self.cache),
            patch("django.contrib.contenttypes.models.ContentType.objects.get_for_model", return_value=SimpleNamespace(pk=8)),
            patch("apps.translations.tasks.generate_automatic_translation_task.apply_async") as publish,
        ):
            self.assertEqual(self._enqueue(), 1)
            self.assertEqual(self._enqueue(), 0)

        publish.assert_called_once()
        kwargs = publish.call_args.kwargs["kwargs"]
        self.assertEqual(kwargs["source_text_hash"], hash_text("Hello world"))
        self.assertEqual(kwargs["viewer_id"], 18)
        self.assertNotIn("Hello world", repr(kwargs))

    @override_settings(TRANSLATIONS_AUTOMATIC_ENABLED=True)
    def test_over_text_limit_is_not_dispatched(self):
        self.presentation["fields"]["caption"]["original"] = "Z" * 3200
        with (
            patch("apps.translations.services.automatic_dispatch._dispatch_cache", return_value=self.cache),
            patch("django.contrib.contenttypes.models.ContentType.objects.get_for_model", return_value=SimpleNamespace(pk=8)),
            patch("apps.translations.tasks.generate_automatic_translation_task.apply_async") as publish,
        ):
            self.assertEqual(self._enqueue(), 0)
        publish.assert_not_called()

    @override_settings(TRANSLATIONS_AUTOMATIC_ENABLED=True)
    def test_broker_failure_releases_dispatch_claim(self):
        with (
            patch("apps.translations.services.automatic_dispatch._dispatch_cache", return_value=self.cache),
            patch("django.contrib.contenttypes.models.ContentType.objects.get_for_model", return_value=SimpleNamespace(pk=8)),
            patch("apps.translations.tasks.generate_automatic_translation_task.apply_async", side_effect=ConnectionError("broker unavailable")),
        ):
            self.assertEqual(self._enqueue(), 0)
        key = automatic_job_key(
            content_type_id=8,
            object_id=51,
            field_name="caption",
            target_language="fa",
            source_text_hash=hash_text("Hello world"),
        )
        self.assertIsNone(self.cache.get(key))

    @override_settings(
        TRANSLATIONS_AUTOMATIC_ENABLED=True,
        TRANSLATIONS_AUTOMATIC_DAILY_USER_LIMIT=1,
    )
    def test_user_daily_cap(self):
        self.obj._meta.model_name = "testimony"
        self.obj._meta.label_lower = "posts.testimony"
        self.obj.type = "written"
        self.presentation["fields"] = {
            "title": {"original": "Title", "status": "missing"},
            "content": {"original": "Body", "status": "missing"},
        }
        with (
            patch("apps.translations.services.automatic_dispatch._dispatch_cache", return_value=self.cache),
            patch("django.contrib.contenttypes.models.ContentType.objects.get_for_model", return_value=SimpleNamespace(pk=8)),
            patch("apps.translations.tasks.generate_automatic_translation_task.apply_async") as publish,
        ):
            self.assertEqual(self._enqueue(), 1)
        publish.assert_called_once()


@override_settings(TRANSLATIONS_AUTOMATIC_ENABLED=True)
class AutomaticTranslationWorkerTests(SimpleTestCase):
    def setUp(self):
        self.cache = LocMemCache("automatic-worker-unit", {})
        self.cache.clear()
        self.viewer = SimpleNamespace(pk=18, is_authenticated=True, primary_language="fa")
        self.obj = SimpleNamespace(
            pk=51,
            caption="Hello world",
            _meta=SimpleNamespace(
                app_label="posts",
                model_name="moment",
                label_lower="posts.moment",
            ),
        )
        self.kwargs = {
            "content_type_id": 8,
            "object_id": 51,
            "field_name": "caption",
            "target_language": "fa",
            "source_text_hash": hash_text("Hello world"),
            "viewer_id": 18,
        }

    def _run_with_mocks(self, *, authorized=True):
        model_queryset = Mock()
        model_queryset.first.return_value = self.obj
        user_queryset = Mock()
        user_queryset.first.return_value = self.viewer
        user_class = SimpleNamespace(objects=Mock())
        user_class.objects.filter.return_value = user_queryset
        content_type = Mock()
        content_type.model_class.return_value = Moment
        with (
            patch("apps.translations.tasks._dispatch_cache", return_value=self.cache),
            patch("apps.translations.tasks.get_user_model", return_value=user_class),
            patch("apps.translations.tasks.ContentType.objects.get_for_id", return_value=content_type),
            patch.object(Moment.objects, "filter", return_value=model_queryset),
            patch("apps.translations.tasks._automatic_authorized_object", return_value=self.obj if authorized else None),
            patch("apps.translations.tasks.translate_cached", return_value={"cached": False}) as translate,
        ):
            outcome = generate_automatic_translation_task.run(**self.kwargs)
        return outcome, translate

    def test_stale_source_is_rejected_before_provider(self):
        self.obj.caption = "Edited after scheduling"
        outcome, translate = self._run_with_mocks()
        self.assertEqual(outcome["status"], "stale_source")
        translate.assert_not_called()

    def test_changed_primary_language_blocks_provider(self):
        self.viewer.primary_language = "fr"
        outcome, translate = self._run_with_mocks()
        self.assertEqual(outcome["status"], "viewer_language_changed")
        translate.assert_not_called()

    def test_changed_permissions_block_provider(self):
        outcome, translate = self._run_with_mocks(authorized=False)
        self.assertEqual(outcome["status"], "access_restricted")
        translate.assert_not_called()

    def test_valid_job_uses_explicit_primary_target_without_humanization(self):
        outcome, translate = self._run_with_mocks()
        self.assertEqual(outcome["status"], "ready")
        translate.assert_called_once_with(
            obj=self.obj,
            field_name="caption",
            user=None,
            target_language="fa",
            source_language=None,
            humanize=False,
        )

    def test_processing_lock_prevents_duplicate_worker(self):
        key = automatic_job_key(
            content_type_id=8,
            object_id=51,
            field_name="caption",
            target_language="fa",
            source_text_hash=hash_text("Hello world"),
        )
        self.cache.add(f"{key}:processing", 1, timeout=180)
        outcome, translate = self._run_with_mocks()
        self.assertEqual(outcome["status"], "already_processing")
        translate.assert_not_called()


class StreamAutomaticDispatchIntegrationTests(SimpleTestCase):
    def setUp(self):
        from apps.core.streams.serializers import StreamItemSerializer

        self.viewer = SimpleNamespace(pk=18, is_authenticated=True, primary_language="fa")
        self.obj = SimpleNamespace(pk=51)
        self.item = SimpleNamespace(kind="moment", obj=self.obj)
        self.serializer = StreamItemSerializer(
            context={"request": SimpleNamespace(user=self.viewer)},
        )
        self.presentation = {
            "target_language": "fa",
            "fields": {"caption": {"original": "Hello", "status": "missing"}},
        }

    def test_missing_field_is_queued_after_cache_presentation(self):
        data = {"caption": "Hello"}
        with (
            patch("apps.core.streams.serializers.cached_automatic_fields", return_value=self.presentation),
            patch("apps.core.streams.serializers.automatic_stream_request_limit", return_value=1),
            patch("apps.core.streams.serializers.dispatch_missing_automatic_fields", return_value=1) as dispatch,
        ):
            self.serializer._attach_automatic_translation(data=data, item=self.item)
            self.assertEqual(
                data["automatic_translation"]["refresh_after_seconds"], 12,
            )
            self.assertEqual(
                data["automatic_translation"]["fields"], self.presentation["fields"],
            )
            dispatch.assert_called_once_with(
                obj=self.obj,
                presentation=self.presentation,
                viewer=self.viewer,
                remaining=1,
            )
            dispatch.reset_mock()
            self.serializer._attach_automatic_translation(
                data={"caption": "Another"}, item=self.item,
            )
            dispatch.assert_not_called()

    def test_anonymous_viewer_does_not_create_translation_presentation(self):
        self.viewer.is_authenticated = False
        data = {"caption": "Hello"}
        with patch("apps.core.streams.serializers.cached_automatic_fields") as cached:
            self.serializer._attach_automatic_translation(data=data, item=self.item)
        self.assertNotIn("automatic_translation", data)
        cached.assert_not_called()

    def test_media_testimony_gets_server_language_without_translation_job(self):
        self.item.kind = "testimony"
        data = {"type": "video", "title": "My Story", "content": None}
        empty_presentation = {"target_language": "fa", "fields": {}}
        with (
            patch(
                "apps.core.streams.serializers.cached_automatic_fields",
                return_value=empty_presentation,
            ) as cached,
            patch(
                "apps.core.streams.serializers.dispatch_missing_automatic_fields",
            ) as dispatch,
        ):
            self.serializer._attach_automatic_translation(data=data, item=self.item)

        self.assertEqual(data["automatic_translation"], empty_presentation)
        cached.assert_called_once_with(obj=self.obj, fields={}, viewer=self.viewer)
        dispatch.assert_not_called()

    def test_refresh_hint_not_exposed_when_dispatch_is_skipped(self):
        data = {"caption": "Hello"}
        with (
            patch("apps.core.streams.serializers.cached_automatic_fields", return_value=self.presentation),
            patch("apps.core.streams.serializers.automatic_stream_request_limit", return_value=1),
            patch("apps.core.streams.serializers.dispatch_missing_automatic_fields", return_value=0),
        ):
            self.serializer._attach_automatic_translation(data=data, item=self.item)

        self.assertNotIn("refresh_after_seconds", data["automatic_translation"])

    def test_prayer_response_receives_own_refresh_hint(self):
        self.item.kind = "pray"
        response = SimpleNamespace(pk=52)
        self.obj.response = response
        data = {"caption": "", "response": {"response_text": "Answered"}}
        response_presentation = {
            "target_language": "fa",
            "fields": {"response_text": {"original": "Answered", "status": "missing"}},
        }

        with (
            patch("apps.core.streams.serializers.cached_automatic_fields", side_effect=[
                {"target_language": "fa", "fields": {}}, response_presentation,
            ]),
            patch("apps.core.streams.serializers.automatic_stream_request_limit", return_value=1),
            patch("apps.core.streams.serializers.dispatch_missing_automatic_fields", side_effect=[0, 1]),
        ):
            self.serializer._attach_automatic_translation(data=data, item=self.item)

        self.assertNotIn("refresh_after_seconds", data["automatic_translation"])
        self.assertEqual(
            data["response"]["automatic_translation"]["refresh_after_seconds"], 12,
        )

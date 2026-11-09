# apps/translations/tests/test_automatic.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-07.
# Last Update by Hossein Sakkaki on 2026-11-07.

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIRequestFactory

from apps.translations.models import ConversationKeyGuidance, TranslationCache
from apps.translations.services.automatic import cached_automatic_fields
from apps.translations.services.hashing import hash_text
from apps.translations.views.moment import MomentTranslationViewSet
from apps.translations.views.prayer import PrayerTranslationViewSet


class AutomaticTranslationCacheTests(TestCase):
    def setUp(self):
        self.content = ConversationKeyGuidance.objects.create(
            slug="backup",
            title="Hello world",
            content="First paragraph.\n\nSecond paragraph.",
        )
        self.viewer = SimpleNamespace(
            is_authenticated=True,
            primary_language="fa",
            secondary_language="fr",
        )

    def cache_translation(
        self, *, field="title", source="Hello world", translated="سلام دنیا", source_language="en",
    ):
        return TranslationCache.objects.create(
            content_type=ContentType.objects.get_for_model(self.content),
            object_id=self.content.pk,
            field_name=field,
            source_language=source_language,
            target_language="fa",
            source_text_hash=hash_text(source),
            translated_text=translated,
        )

    def test_uses_primary_language_and_preserves_original(self):
        self.cache_translation()
        response = cached_automatic_fields(
            obj=self.content, fields={"title": self.content.title}, viewer=self.viewer,
        )
        self.assertEqual(response["target_language"], "fa")
        self.assertEqual(response["fields"]["title"], {
            "original": "Hello world",
            "translated": "سلام دنیا",
            "source_language": "en",
            "status": "ready",
        })

    def test_regular_automatic_reads_keep_cached_translation_fresh(self):
        row = self.cache_translation()
        old_date = timezone.now() - timedelta(days=2)
        TranslationCache.objects.filter(pk=row.pk).update(last_accessed_at=old_date)
        cached_automatic_fields(
            obj=self.content, fields={"title": self.content.title}, viewer=self.viewer,
        )
        row.refresh_from_db()
        self.assertGreater(row.last_accessed_at, old_date)

    def test_does_not_use_stale_content_hash(self):
        self.cache_translation()
        response = cached_automatic_fields(
            obj=self.content, fields={"title": "Updated title"}, viewer=self.viewer,
        )
        self.assertEqual(response["fields"]["title"]["status"], "missing")
        self.assertIsNone(response["fields"]["title"]["translated"])

    def test_same_language_is_original(self):
        self.cache_translation(source_language="fa", translated="Hello world")
        response = cached_automatic_fields(
            obj=self.content, fields={"title": self.content.title}, viewer=self.viewer,
        )
        self.assertEqual(response["fields"]["title"]["status"], "original")
        self.assertIsNone(response["fields"]["title"]["translated"])

    def test_invalid_cached_paragraph_structure_is_not_presented(self):
        self.cache_translation(
            field="content",
            source=self.content.content,
            translated="One paragraph only",
        )
        response = cached_automatic_fields(
            obj=self.content, fields={"content": self.content.content}, viewer=self.viewer,
        )
        self.assertEqual(response["fields"]["content"]["status"], "missing")

    def test_missing_cache_does_not_enqueue_or_translate(self):
        with patch("apps.translations.services.aws_translate.AWSTranslateClient") as aws:
            response = cached_automatic_fields(
                obj=self.content, fields={"title": self.content.title}, viewer=self.viewer,
            )
        self.assertEqual(response["fields"]["title"]["status"], "missing")
        aws.assert_not_called()

    def test_change_of_primary_language_does_not_reuse_previous_target(self):
        self.cache_translation()
        self.viewer.primary_language = "fr"
        response = cached_automatic_fields(
            obj=self.content, fields={"title": self.content.title}, viewer=self.viewer,
        )
        self.assertEqual(response["target_language"], "fr")
        self.assertEqual(response["fields"]["title"]["status"], "missing")

    def test_anonymous_viewer_cannot_use_automatic_cache(self):
        self.viewer.is_authenticated = False
        with self.assertRaises(ValueError):
            cached_automatic_fields(
                obj=self.content, fields={"title": self.content.title}, viewer=self.viewer,
            )


class VisibilityFailureClosedTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_moment_translation_never_runs_if_visibility_raises(self):
        content = SimpleNamespace(
            pk=101,
            caption="Original caption",
        )
        view = MomentTranslationViewSet.as_view({"post": "translate_caption"})
        with (
            patch.object(MomentTranslationViewSet, "get_object", return_value=content),
            patch("apps.translations.views.moment.translate_cached") as translate,
            patch("apps.translations.views.moment.VisibilityPolicy.gate_reason", side_effect=RuntimeError("unavailable")),
        ):
            response = view(
                self.factory.post("/translations/moments/test/translate-caption/", {}),
                slug="test",
            )
        self.assertEqual(response.status_code, 503)
        translate.assert_not_called()

    def test_prayer_caption_translation_never_runs_if_visibility_raises(self):
        content = SimpleNamespace(
            pk=102,
            caption="Original caption",
        )
        view = PrayerTranslationViewSet.as_view({"post": "translate_caption"})
        with (
            patch.object(PrayerTranslationViewSet, "get_object", return_value=content),
            patch("apps.translations.views.prayer.translate_cached") as translate,
            patch("apps.translations.views.prayer.VisibilityPolicy.gate_reason", side_effect=RuntimeError("unavailable")),
        ):
            response = view(
                self.factory.post("/translations/prayers/test/translate-caption/", {}),
                slug="test",
            )
        self.assertEqual(response.status_code, 503)
        translate.assert_not_called()

    def test_prayer_response_translation_never_runs_if_visibility_raises(self):
        content = SimpleNamespace(
            pk=103,
            response=SimpleNamespace(response_text="Original response"),
        )
        view = PrayerTranslationViewSet.as_view({"post": "translate_response"})
        with (
            patch.object(PrayerTranslationViewSet, "get_object", return_value=content),
            patch("apps.translations.views.prayer.translate_cached") as translate,
            patch("apps.translations.views.prayer.VisibilityPolicy.gate_reason", side_effect=RuntimeError("unavailable")),
        ):
            response = view(
                self.factory.post("/translations/prayers/test/translate-response/", {}),
                slug="test",
            )
        self.assertEqual(response.status_code, 503)
        translate.assert_not_called()

from __future__ import annotations

import inspect
import tempfile
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import SimpleTestCase

from apps.media_conversion.models import MediaJobKind
from apps.media_conversion.services import storage_cleanup
from apps.posts.signals import moment_media_cleanup
from apps.posts.signals import prayer_media_cleanup
from apps.posts.signals import testimony_media_cleanup
from apps.subtitles.services import testimony_enforcement


class FakeQuerySet(list):
    def __init__(self, values=()):
        super().__init__(values)
        self.delete_called = False

    def delete(self):
        self.delete_called = True


class DummyField:
    def __init__(self, name: str, storage):
        self.name = name
        self.storage = storage

    def __bool__(self):
        return bool(self.name)


class CrossModuleStorageCleanupSafetyTests(SimpleTestCase):
    def setUp(self):
        super().setUp()

        self.temp_dir = tempfile.TemporaryDirectory()

        self.storage = FileSystemStorage(
            location=self.temp_dir.name,
        )

    def tearDown(self):
        self.temp_dir.cleanup()
        super().tearDown()

    # ---------------------------------------------------------
    # Storage helpers
    # ---------------------------------------------------------
    def _put(
        self,
        key: str,
        payload: bytes = b"test-data",
    ):
        saved = self.storage.save(
            key,
            ContentFile(payload),
        )

        self.assertEqual(saved, key)
        self.assertTrue(
            self.storage.exists(key),
        )

        return key

    def _assert_exists(self, *keys):
        for key in keys:
            self.assertTrue(
                self.storage.exists(key),
                f"Expected to survive: {key}",
            )

    def _assert_missing(self, *keys):
        for key in keys:
            self.assertFalse(
                self.storage.exists(key),
                f"Expected to be deleted: {key}",
            )

    def _hls_bundle(
        self,
        *,
        prefix: str,
        asset_uuid: str,
    ):
        root = f"{prefix}/{asset_uuid}"

        keys = [
            f"{root}/master.m3u8",
            f"{root}/preview.mp4",
            f"{root}/source/playlist.m3u8",
            f"{root}/source/seg_000.ts",
            f"{root}/source/seg_001.ts",
            f"{root}/720p/playlist.m3u8",
            f"{root}/720p/seg_000.ts",
        ]

        for key in keys:
            self._put(key)

        return keys[0], keys

    # ---------------------------------------------------------
    # 1. Shared helper: valid UUID HLS isolation
    # ---------------------------------------------------------
    def test_shared_video_cleanup_deletes_only_requested_uuid_tree(
        self,
    ):
        prefix = "posts/videos/moment/2026/08/25"

        canceled_master, canceled_keys = self._hls_bundle(
            prefix=prefix,
            asset_uuid=(
                "11111111-1111-4111-8111-111111111111"
            ),
        )

        victim_master, victim_keys = self._hls_bundle(
            prefix=prefix,
            asset_uuid=(
                "22222222-2222-4222-8222-222222222222"
            ),
        )

        storage_cleanup.delete_video_output(
            canceled_master,
            label="test.shared-hls",
            storage=self.storage,
        )

        self._assert_missing(*canceled_keys)

        self._assert_exists(
            victim_master,
            *victim_keys,
        )

    # ---------------------------------------------------------
    # 2. Shared helper: malformed shared-parent HLS is blocked
    # ---------------------------------------------------------
    def test_shared_video_cleanup_blocks_date_directory_recursion(
        self,
    ):
        prefix = "posts/videos/moment/2026/08/25"

        unsafe_master = f"{prefix}/master.m3u8"
        victim_a = f"{prefix}/victim-a.mp4"
        victim_b = f"{prefix}/nested/victim-b.ts"

        self._put(unsafe_master)
        self._put(victim_a)
        self._put(victim_b)

        storage_cleanup.delete_video_output(
            unsafe_master,
            label="test.unsafe-shared-hls",
            storage=self.storage,
        )

        self._assert_missing(
            unsafe_master,
        )

        self._assert_exists(
            victim_a,
            victim_b,
        )

    # ---------------------------------------------------------
    # 3. Moment FileField cleanup
    # ---------------------------------------------------------
    def test_moment_video_field_cleanup_does_not_delete_sibling_hls(
        self,
    ):
        prefix = "posts/videos/moment/2026/08/25"

        canceled_master, canceled_keys = self._hls_bundle(
            prefix=prefix,
            asset_uuid=(
                "33333333-3333-4333-8333-333333333333"
            ),
        )

        victim_master, victim_keys = self._hls_bundle(
            prefix=prefix,
            asset_uuid=(
                "44444444-4444-4444-8444-444444444444"
            ),
        )

        field = DummyField(
            canceled_master,
            self.storage,
        )

        moment_media_cleanup._safe_delete_filefield(
            field,
            "video",
        )

        self._assert_missing(*canceled_keys)

        self._assert_exists(
            victim_master,
            *victim_keys,
        )

    # ---------------------------------------------------------
    # 4. Moment MediaConversionJob cleanup
    # ---------------------------------------------------------
    def test_moment_job_cleanup_does_not_delete_same_day_siblings(
        self,
    ):
        prefix = "posts/videos/moment/2026/08/25"

        canceled_master, canceled_keys = self._hls_bundle(
            prefix=prefix,
            asset_uuid=(
                "55555555-5555-4555-8555-555555555555"
            ),
        )

        victim_master, victim_keys = self._hls_bundle(
            prefix=prefix,
            asset_uuid=(
                "66666666-6666-4666-8666-666666666666"
            ),
        )

        source = f"{prefix}/raw-source.mov"
        self._put(source)

        job = SimpleNamespace(
            source_path=source,
            output_path=canceled_master,
            kind=MediaJobKind.VIDEO,
        )

        jobs_qs = FakeQuerySet([job])

        with (
            patch.object(
                storage_cleanup,
                "default_storage",
                self.storage,
            ),
            patch.object(
                moment_media_cleanup.ContentType.objects,
                "get_for_model",
                return_value=object(),
            ),
            patch.object(
                moment_media_cleanup.MediaConversionJob.objects,
                "filter",
                return_value=jobs_qs,
            ),
        ):
            moment_media_cleanup._delete_media_conversion_paths(
                SimpleNamespace(pk=101)
            )

        self.assertTrue(jobs_qs.delete_called)

        self._assert_missing(
            source,
            *canceled_keys,
        )

        self._assert_exists(
            victim_master,
            *victim_keys,
        )

    # ---------------------------------------------------------
    # 5. Prayer MediaConversionJob cleanup
    # ---------------------------------------------------------
    def test_prayer_job_cleanup_does_not_delete_same_day_siblings(
        self,
    ):
        prefix = "posts/videos/prayer/2026/08/25"

        canceled_master, canceled_keys = self._hls_bundle(
            prefix=prefix,
            asset_uuid=(
                "77777777-7777-4777-8777-777777777777"
            ),
        )

        victim_master, victim_keys = self._hls_bundle(
            prefix=prefix,
            asset_uuid=(
                "88888888-8888-4888-8888-888888888888"
            ),
        )

        source = f"{prefix}/raw-source.mov"
        self._put(source)

        job = SimpleNamespace(
            source_path=source,
            output_path=canceled_master,
            kind=MediaJobKind.VIDEO,
        )

        jobs_qs = FakeQuerySet([job])

        dummy_model = type(
            "DummyPrayer",
            (),
            {},
        )

        with (
            patch.object(
                storage_cleanup,
                "default_storage",
                self.storage,
            ),
            patch.object(
                prayer_media_cleanup.ContentType.objects,
                "get_for_model",
                return_value=object(),
            ),
            patch.object(
                prayer_media_cleanup.MediaConversionJob.objects,
                "filter",
                return_value=jobs_qs,
            ),
        ):
            prayer_media_cleanup._cleanup_conversion_jobs(
                dummy_model,
                202,
            )

        self.assertTrue(jobs_qs.delete_called)

        self._assert_missing(
            source,
            *canceled_keys,
        )

        self._assert_exists(
            victim_master,
            *victim_keys,
        )

    # ---------------------------------------------------------
    # 6. Testimony post_delete cleanup
    # ---------------------------------------------------------
    def test_testimony_delete_signal_does_not_delete_same_day_siblings(
        self,
    ):
        prefix = "posts/videos/testimony/2026/08/25"

        canceled_master, canceled_keys = self._hls_bundle(
            prefix=prefix,
            asset_uuid=(
                "99999999-9999-4999-8999-999999999999"
            ),
        )

        victim_master, victim_keys = self._hls_bundle(
            prefix=prefix,
            asset_uuid=(
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            ),
        )

        source = f"{prefix}/raw-source.mov"
        self._put(source)

        job = SimpleNamespace(
            source_path=source,
            output_path=canceled_master,
            kind=MediaJobKind.VIDEO,
        )

        jobs_qs = FakeQuerySet([job])

        instance = SimpleNamespace(
            pk=303,
            audio=None,
            video=None,
            thumbnail=None,
            audio_artwork=None,
        )

        with (
            patch.object(
                storage_cleanup,
                "default_storage",
                self.storage,
            ),
            patch.object(
                testimony_media_cleanup.transaction,
                "on_commit",
                side_effect=lambda callback: callback(),
            ),
            patch.object(
                testimony_media_cleanup.ContentType.objects,
                "get_for_model",
                return_value=object(),
            ),
            patch.object(
                testimony_media_cleanup.MediaConversionJob.objects,
                "filter",
                return_value=jobs_qs,
            ),
            patch.object(
                testimony_media_cleanup,
                "_cleanup_subtitles_for_testimony",
                return_value=None,
            ),
        ):
            testimony_media_cleanup.testimony_cleanup_media_on_delete(
                sender=None,
                instance=instance,
            )

        self.assertTrue(jobs_qs.delete_called)

        self._assert_missing(
            source,
            *canceled_keys,
        )

        self._assert_exists(
            victim_master,
            *victim_keys,
        )

    # ---------------------------------------------------------
    # 7. Rejected Testimony enforcement
    # ---------------------------------------------------------
    def test_rejected_testimony_enforcement_cannot_wipe_sibling_media(
        self,
    ):
        video_prefix = (
            "posts/videos/testimony/2026/08/25"
        )

        image_prefix = (
            "posts/photos/testimony/2026/08/25"
        )

        canceled_master, canceled_keys = self._hls_bundle(
            prefix=video_prefix,
            asset_uuid=(
                "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            ),
        )

        victim_master, victim_keys = self._hls_bundle(
            prefix=video_prefix,
            asset_uuid=(
                "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
            ),
        )

        rejected_image = (
            f"{image_prefix}/"
            "dddddddd-dddd-4ddd-8ddd-dddddddddddd.jpg"
        )

        victim_image = (
            f"{image_prefix}/"
            "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee.jpg"
        )

        job_source = (
            f"{video_prefix}/raw-source.mov"
        )

        stt_audio = (
            "posts/audios/testimony/"
            "stt/303/audio.wav"
        )

        voice_audio = (
            "posts/audios/testimony/"
            "voices/voice-1.mp3"
        )

        for key in (
            rejected_image,
            victim_image,
            job_source,
            stt_audio,
            voice_audio,
        ):
            self._put(key)

        content_type = SimpleNamespace(
            app_label="posts",
            model="testimony",
        )

        transcript = SimpleNamespace(
            pk=404,
            content_type=content_type,
            object_id=303,
            content_review_reason="Rejected for test",
            stt_audio=stt_audio,
            delete=MagicMock(),
        )

        target = SimpleNamespace(
            pk=303,
            delete=MagicMock(),
        )

        transcript_lookup = MagicMock()
        transcript_lookup.filter.return_value.first.return_value = (
            transcript
        )

        voice_lookup = MagicMock()
        voice_lookup.exclude.return_value.values_list.return_value = [
            voice_audio
        ]

        job_lookup = MagicMock()
        job_lookup.values_list.return_value = [
            (
                MediaJobKind.VIDEO,
                job_source,
                canceled_master,
            )
        ]

        with (
            patch.object(
                storage_cleanup,
                "default_storage",
                self.storage,
            ),
            patch.object(
                testimony_enforcement.VideoTranscript.objects,
                "select_related",
                return_value=transcript_lookup,
            ),
            patch.object(
                testimony_enforcement.VoiceTrack.objects,
                "filter",
                return_value=voice_lookup,
            ),
            patch.object(
                testimony_enforcement.MediaConversionJob.objects,
                "filter",
                return_value=job_lookup,
            ),
            patch.object(
                testimony_enforcement.transaction,
                "atomic",
                return_value=nullcontext(),
            ),
            patch.object(
                testimony_enforcement,
                "_is_posts_testimony_transcript",
                return_value=True,
            ),
            patch.object(
                testimony_enforcement,
                "_safe_target_for_transcript",
                return_value=target,
            ),
            patch.object(
                testimony_enforcement,
                "_resolve_owner_user",
                return_value=None,
            ),
            patch.object(
                testimony_enforcement,
                "_notify_user_about_rejected_testimony",
                return_value=None,
            ),
            patch.object(
                testimony_enforcement,
                "_target_field_keys",
                return_value=[rejected_image],
            ),
        ):
            testimony_enforcement.delete_rejected_testimony_media(
                transcript,
                reason="Rejected for regression test",
            )

        self._assert_missing(
            rejected_image,
            job_source,
            stt_audio,
            voice_audio,
            *canceled_keys,
        )

        self._assert_exists(
            victim_image,
            victim_master,
            *victim_keys,
        )

        transcript.delete.assert_called_once()
        target.delete.assert_called_once()
        job_lookup.delete.assert_called_once()

    # ---------------------------------------------------------
    # 8. Static regression guard
    # ---------------------------------------------------------
    def test_cleanup_modules_do_not_reintroduce_raw_prefix_delete(
        self,
    ):
        modules = (
            moment_media_cleanup,
            prayer_media_cleanup,
            testimony_media_cleanup,
            testimony_enforcement,
        )

        combined = "\n".join(
            inspect.getsource(module)
            for module in modules
        )

        forbidden = (
            "bucket.objects.filter",
            "Prefix=",
            "_safe_delete_prefix",
            "_delete_storage_tree",
            "_delete_prefix_recursive",
        )

        for token in forbidden:
            self.assertNotIn(
                token,
                combined,
                (
                    "Unsafe storage cleanup pattern "
                    f"reintroduced: {token}"
                ),
            )
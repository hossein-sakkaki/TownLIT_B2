from __future__ import annotations

import tempfile
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import SimpleTestCase

from apps.media_conversion.models import (
    MediaJobKind,
    MediaJobStatus,
)
from apps.media_conversion.services import cancellation
from apps.media_conversion.services.image_variants import (
    IMAGE_VARIANT_WIDTHS,
)
from apps.media_conversion.tasks import base as base_tasks
from apps.media_conversion.tasks import image as image_tasks
from apps.media_conversion.tasks import video as video_tasks


class StorageCleanupSafetyTests(SimpleTestCase):
    """
    Regression coverage for destructive media cleanup.

    IMPORTANT:
    These tests use a temporary local FileSystemStorage.
    They must never touch configured S3/default_storage.
    """

    def setUp(self):
        super().setUp()

        self.temp_dir = tempfile.TemporaryDirectory()

        self.storage = FileSystemStorage(
            location=self.temp_dir.name,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

        super().tearDown()

    # ------------------------------------------------------------------
    # Generic test storage helpers
    # ------------------------------------------------------------------
    def _put(
        self,
        key: str,
        payload: bytes = b"test-data",
    ) -> str:
        saved = self.storage.save(
            key,
            ContentFile(payload),
        )

        self.assertEqual(
            saved,
            key,
            (
                "Test fixture unexpectedly changed "
                f"storage key: {key} -> {saved}"
            ),
        )

        self.assertTrue(
            self.storage.exists(key),
            f"Failed to create test object: {key}",
        )

        return key

    def _assert_exists(
        self,
        *keys: str,
    ) -> None:
        for key in keys:
            self.assertTrue(
                self.storage.exists(key),
                f"Expected storage object to survive: {key}",
            )

    def _assert_missing(
        self,
        *keys: str,
    ) -> None:
        for key in keys:
            self.assertFalse(
                self.storage.exists(key),
                f"Expected storage object to be deleted: {key}",
            )

    def _image_bundle(
        self,
        *,
        prefix: str,
        asset_uuid: str,
    ) -> tuple[str, list[str]]:
        output = (
            f"{prefix}/"
            f"{asset_uuid}.jpg"
        )

        variants = [
            (
                f"{prefix}/variants/"
                f"{asset_uuid}_{variant_name}.jpg"
            )
            for variant_name in IMAGE_VARIANT_WIDTHS
        ]

        self._put(
            output
        )

        for key in variants:
            self._put(
                key
            )

        return (
            output,
            variants,
        )

    def _hls_bundle(
        self,
        *,
        prefix: str,
        asset_uuid: str,
    ) -> tuple[str, list[str]]:
        root = (
            f"{prefix}/"
            f"{asset_uuid}"
        )

        keys = [
            f"{root}/master.m3u8",
            f"{root}/preview.mp4",
            f"{root}/source/playlist.m3u8",
            f"{root}/source/seg_000.ts",
            f"{root}/source/seg_001.ts",
            f"{root}/720p/playlist.m3u8",
            f"{root}/720p/seg_000.ts",
            f"{root}/720p/seg_001.ts",
        ]

        for key in keys:
            self._put(
                key
            )

        return (
            keys[0],
            keys,
        )

    # ------------------------------------------------------------------
    # 1. Service-level image regression
    # ------------------------------------------------------------------
    def test_image_output_cleanup_never_deletes_sibling_assets(
        self,
    ):
        """
        Exact reproduction of the Aug-25 failure shape:

        same date prefix:
            victim A
            canceled asset
            victim B

        Cleaning the canceled image must not delete either victim.
        """

        prefix = (
            "posts/images/moment/"
            "2026/08/25"
        )

        victim_a_output, victim_a_variants = (
            self._image_bundle(
                prefix=prefix,
                asset_uuid=(
                    "11111111-1111-4111-8111-"
                    "111111111111"
                ),
            )
        )

        canceled_output, canceled_variants = (
            self._image_bundle(
                prefix=prefix,
                asset_uuid=(
                    "22222222-2222-4222-8222-"
                    "222222222222"
                ),
            )
        )

        victim_b_output, victim_b_variants = (
            self._image_bundle(
                prefix=prefix,
                asset_uuid=(
                    "33333333-3333-4333-8333-"
                    "333333333333"
                ),
            )
        )

        with patch.object(
            cancellation,
            "default_storage",
            self.storage,
        ):
            cancellation._delete_image_output_bundle(
                canceled_output,
                label="test.image",
            )

        self._assert_missing(
            canceled_output,
            *canceled_variants,
        )

        self._assert_exists(
            victim_a_output,
            *victim_a_variants,
            victim_b_output,
            *victim_b_variants,
        )

    # ------------------------------------------------------------------
    # 2. Worker-level image regression
    # ------------------------------------------------------------------
    def test_image_worker_cleanup_never_deletes_sibling_assets(
        self,
    ):
        prefix = (
            "posts/images/moment/"
            "2026/08/25"
        )

        victim_output, victim_variants = (
            self._image_bundle(
                prefix=prefix,
                asset_uuid=(
                    "44444444-4444-4444-8444-"
                    "444444444444"
                ),
            )
        )

        canceled_output, canceled_variants = (
            self._image_bundle(
                prefix=prefix,
                asset_uuid=(
                    "55555555-5555-4555-8555-"
                    "555555555555"
                ),
            )
        )

        with patch.object(
            image_tasks,
            "default_storage",
            self.storage,
        ):
            image_tasks._safe_delete_generated_image_bundle(
                canceled_output
            )

        self._assert_missing(
            canceled_output,
            *canceled_variants,
        )

        self._assert_exists(
            victim_output,
            *victim_variants,
        )

    # ------------------------------------------------------------------
    # 3. Service-level valid HLS tree
    # ------------------------------------------------------------------
    def test_hls_cleanup_deletes_only_requested_uuid_tree(
        self,
    ):
        prefix = (
            "posts/videos/moment/"
            "2026/08/25"
        )

        canceled_master, canceled_keys = (
            self._hls_bundle(
                prefix=prefix,
                asset_uuid=(
                    "aaaaaaaa-aaaa-4aaa-8aaa-"
                    "aaaaaaaaaaaa"
                ),
            )
        )

        victim_master, victim_keys = (
            self._hls_bundle(
                prefix=prefix,
                asset_uuid=(
                    "bbbbbbbb-bbbb-4bbb-8bbb-"
                    "bbbbbbbbbbbb"
                ),
            )
        )

        with patch.object(
            cancellation,
            "default_storage",
            self.storage,
        ):
            cancellation._delete_hls_output_tree(
                canceled_master,
                label="test.hls",
            )

        self._assert_missing(
            *canceled_keys,
        )

        self._assert_exists(
            victim_master,
            *victim_keys,
        )

    # ------------------------------------------------------------------
    # 4. Critical fail-closed HLS test
    # ------------------------------------------------------------------
    def test_hls_cleanup_refuses_recursive_delete_for_shared_date_prefix(
        self,
    ):
        """
        A malformed path such as:

            .../2026/08/25/master.m3u8

        must NEVER authorize recursive deletion of:

            .../2026/08/25/

        Exact master deletion is acceptable.
        Sibling objects must survive.
        """

        prefix = (
            "posts/videos/moment/"
            "2026/08/25"
        )

        unsafe_master = (
            f"{prefix}/master.m3u8"
        )

        victim_video = (
            f"{prefix}/"
            "victim-production.mp4"
        )

        victim_nested = (
            f"{prefix}/"
            "unrelated/source/seg_000.ts"
        )

        self._put(
            unsafe_master
        )

        self._put(
            victim_video
        )

        self._put(
            victim_nested
        )

        with patch.object(
            cancellation,
            "default_storage",
            self.storage,
        ):
            cancellation._delete_hls_output_tree(
                unsafe_master,
                label="test.unsafe_hls",
            )

        # Exact master may be removed.
        self._assert_missing(
            unsafe_master
        )

        # Shared date-prefix contents MUST survive.
        self._assert_exists(
            victim_video,
            victim_nested,
        )

    # ------------------------------------------------------------------
    # 5. Direct recursive guard
    # ------------------------------------------------------------------
    def test_uuid_tree_guard_blocks_date_directory(
        self,
    ):
        prefix = (
            "posts/images/moment/"
            "2026/08/25"
        )

        victim_a = (
            f"{prefix}/"
            "victim-a.jpg"
        )

        victim_b = (
            f"{prefix}/variants/"
            "victim-b_feed.jpg"
        )

        self._put(
            victim_a
        )

        self._put(
            victim_b
        )

        with patch.object(
            cancellation,
            "default_storage",
            self.storage,
        ):
            cancellation._delete_uuid_scoped_tree(
                prefix,
                label="test.block_date_prefix",
            )

        self._assert_exists(
            victim_a,
            victim_b,
        )

    # ------------------------------------------------------------------
    # 6. Worker-level valid HLS tree
    # ------------------------------------------------------------------
    def test_video_worker_cleanup_deletes_only_own_uuid_tree(
        self,
    ):
        prefix = (
            "posts/videos/moment/"
            "2026/08/25"
        )

        canceled_master, canceled_keys = (
            self._hls_bundle(
                prefix=prefix,
                asset_uuid=(
                    "cccccccc-cccc-4ccc-8ccc-"
                    "cccccccccccc"
                ),
            )
        )

        victim_master, victim_keys = (
            self._hls_bundle(
                prefix=prefix,
                asset_uuid=(
                    "dddddddd-dddd-4ddd-8ddd-"
                    "dddddddddddd"
                ),
            )
        )

        with patch.object(
            video_tasks,
            "default_storage",
            self.storage,
        ):
            video_tasks._safe_delete_video_output(
                canceled_master
            )

        self._assert_missing(
            *canceled_keys,
        )

        self._assert_exists(
            victim_master,
            *victim_keys,
        )

    # ------------------------------------------------------------------
    # 7. Worker-level unsafe HLS guard
    # ------------------------------------------------------------------
    def test_video_worker_refuses_shared_parent_recursive_delete(
        self,
    ):
        prefix = (
            "posts/videos/moment/"
            "2026/08/25"
        )

        unsafe_master = (
            f"{prefix}/master.m3u8"
        )

        victim_a = (
            f"{prefix}/victim-a.mp4"
        )

        victim_b = (
            f"{prefix}/nested/victim-b.ts"
        )

        self._put(
            unsafe_master
        )

        self._put(
            victim_a
        )

        self._put(
            victim_b
        )

        with patch.object(
            video_tasks,
            "default_storage",
            self.storage,
        ):
            video_tasks._safe_delete_video_output(
                unsafe_master
            )

        self._assert_missing(
            unsafe_master
        )

        self._assert_exists(
            victim_a,
            victim_b,
        )

    # ------------------------------------------------------------------
    # 8. Public cancellation regression
    # ------------------------------------------------------------------
    def test_public_cancel_cleanup_cannot_wipe_unrelated_same_day_media(
        self,
    ):
        """
        High-value regression for the real incident shape.

        Simulates:
        - canceled VIDEO job
        - whole unconverted target cleanup
        - target owns multiple image objects
        - unrelated production-style image exists under same date prefix
        - another HLS conversion exists under the same video date prefix

        The canceled target's media may be deleted.
        Unrelated siblings MUST survive.
        """

        image_prefix = (
            "posts/images/moment/"
            "2026/08/25"
        )

        video_prefix = (
            "posts/videos/moment/"
            "2026/08/25"
        )

        # Unrelated production-style image.
        victim_output, victim_variants = (
            self._image_bundle(
                prefix=image_prefix,
                asset_uuid=(
                    "9949bfdc-6ba0-4b97-a766-"
                    "cf616d01f90a"
                ),
            )
        )

        # Media explicitly owned by canceled target.
        target_output, target_variants = (
            self._image_bundle(
                prefix=image_prefix,
                asset_uuid=(
                    "eeeeeeee-eeee-4eee-8eee-"
                    "eeeeeeeeeeee"
                ),
            )
        )

        canceled_master, canceled_hls_keys = (
            self._hls_bundle(
                prefix=video_prefix,
                asset_uuid=(
                    "ffffffff-ffff-4fff-8fff-"
                    "ffffffffffff"
                ),
            )
        )

        sibling_master, sibling_hls_keys = (
            self._hls_bundle(
                prefix=video_prefix,
                asset_uuid=(
                    "12345678-1234-4234-8234-"
                    "123456789abc"
                ),
            )
        )

        source_path = (
            f"{video_prefix}/"
            "raw-source.mov"
        )

        self._put(
            source_path
        )

        target_keys = {
            target_output,
            *target_variants,
        }

        snapshot = SimpleNamespace(
            pk=9001,
            task_id="task-generation-1",
            attempt=1,
        )

        authoritative = SimpleNamespace(
            pk=9001,
            status=MediaJobStatus.CANCELED,
            task_id="task-generation-1",
            attempt=1,
            content_type=SimpleNamespace(
                app_label="posts",
                model="moment",
            ),
            source_path=source_path,
            output_path=canceled_master,
            kind=MediaJobKind.VIDEO,
            field_name="video",
        )

        class DummyTarget:
            pk = 261

            def __init__(self):
                self.was_deleted = False

            def delete(self):
                self.was_deleted = True

        target = DummyTarget()

        queryset = MagicMock()

        queryset.select_related.return_value = (
            queryset
        )

        queryset.filter.return_value = (
            queryset
        )

        queryset.first.return_value = (
            authoritative
        )

        with (
            patch.object(
                cancellation,
                "default_storage",
                self.storage,
            ),
            patch.object(
                cancellation.transaction,
                "atomic",
                return_value=nullcontext(),
            ),
            patch.object(
                cancellation.MediaConversionJob.objects,
                "select_for_update",
                return_value=queryset,
            ),
            patch.object(
                cancellation,
                "_safe_get_target",
                return_value=target,
            ),
            patch.object(
                cancellation,
                "_should_delete_unconverted_target",
                return_value=True,
            ),
            patch.object(
                cancellation,
                "_target_cleanup_keys",
                return_value=target_keys,
            ),
        ):
            cancellation.cleanup_canceled_media_job(
                snapshot,
                reason="regression-test",
                delete_job=False,
                delete_unconverted_target=True,
            )

        self.assertTrue(
            target.was_deleted,
            "Expected canceled unconverted target to be deleted.",
        )

        # Canceled job/target media may disappear.
        self._assert_missing(
            source_path,
            *canceled_hls_keys,
            target_output,
            *target_variants,
        )

        # The actual incident invariant:
        # unrelated media under SAME DATE prefix must survive.
        self._assert_exists(
            victim_output,
            *victim_variants,
            sibling_master,
            *sibling_hls_keys,
        )

    # ------------------------------------------------------------------
    # 9. Same-generation guard
    # ------------------------------------------------------------------
    def test_cancellation_cleanup_requires_same_job_generation(
        self,
    ):
        snapshot = SimpleNamespace(
            task_id="task-a",
            attempt=4,
        )

        same = SimpleNamespace(
            task_id="task-a",
            attempt=4,
        )

        different_task = SimpleNamespace(
            task_id="task-b",
            attempt=4,
        )

        different_attempt = SimpleNamespace(
            task_id="task-a",
            attempt=5,
        )

        self.assertTrue(
            cancellation._same_job_generation(
                snapshot=snapshot,
                authoritative=same,
            )
        )

        self.assertFalse(
            cancellation._same_job_generation(
                snapshot=snapshot,
                authoritative=different_task,
            )
        )

        self.assertFalse(
            cancellation._same_job_generation(
                snapshot=snapshot,
                authoritative=different_attempt,
            )
        )

    # ------------------------------------------------------------------
    # 10. Deleted job must be terminal to worker
    # ------------------------------------------------------------------
    def test_missing_authoritative_job_is_treated_as_canceled(
        self,
    ):
        stale_job = SimpleNamespace(
            pk=77,
        )

        with patch.object(
            base_tasks,
            "_get_authoritative_job",
            return_value=None,
        ):
            self.assertTrue(
                base_tasks.is_job_canceled(
                    stale_job
                )
            )

            self.assertFalse(
                base_tasks.is_job_current_task(
                    stale_job
                )
            )

            with self.assertRaises(
                base_tasks.MediaConversionCanceled
            ):
                base_tasks.raise_if_job_canceled(
                    stale_job
                )

    # ------------------------------------------------------------------
    # 11. Old Celery task must not own reused job
    # ------------------------------------------------------------------
    def test_old_worker_is_rejected_when_task_id_changes(
        self,
    ):
        stale_job = SimpleNamespace(
            pk=88,
        )

        authoritative = SimpleNamespace(
            pk=88,
            task_id="new-task-id",
            status=MediaJobStatus.PROCESSING,
        )

        with (
            patch.object(
                base_tasks,
                "_get_authoritative_job",
                return_value=authoritative,
            ),
            patch.object(
                base_tasks,
                "get_current_task_id",
                return_value="old-task-id",
            ),
        ):
            with self.assertRaises(
                base_tasks.MediaConversionTaskSuperseded
            ):
                base_tasks.raise_if_job_canceled(
                    stale_job
                )

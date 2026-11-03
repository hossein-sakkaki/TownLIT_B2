# apps/media_conversion/management/commands/backfill_testimony_video_previews.py
# TownLIT Backend
#
# Created by Hossein Sakkaki on 2026-11-02.
# Last Update by Hossein Sakkaki on 2026-11-02.

"""Repair missing video previews on converted, existing Testimony HLS assets."""

from __future__ import annotations

import logging
import posixpath
import tempfile
import uuid
from copy import deepcopy

from django.apps import apps
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.media_conversion.services.hls_preview_source import (
    HLSPreviewSourceError,
    safe_storage_key,
    select_hls_segments,
    stage_hls_preview_source,
)
from apps.media_conversion.services.video_preview import build_video_preview_mp4

logger = logging.getLogger(__name__)
PREVIEW_SECONDS = 3.5
PREVIEW_WIDTH = 360


class Command(BaseCommand):
    help = (
        "Backfill short Square/Stream preview MP4s for converted video "
        "testimonies without media_assets.video.preview. Dry-run by default."
    )

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument(
            "--ids", type=int, nargs="+", metavar="ID",
            help="Explicit Testimony IDs, e.g. --ids 199 107",
        )
        target.add_argument(
            "--all", action="store_true",
            help="Scan converted video testimonies; use --limit to batch safely",
        )
        parser.add_argument(
            "--limit", type=int, default=20,
            help="Maximum eligible testimonies per invocation (default 20)",
        )
        parser.add_argument(
            "--apply", action="store_true",
            help="Generate MP4 objects and update DB. Omit for dry-run",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 100:
            raise CommandError("--limit must be between 1 and 100")

        ids = options["ids"]
        if ids and (min(ids) <= 0 or len(set(ids)) != len(ids)):
            raise CommandError("--ids must contain unique positive integers")
        if ids and len(ids) > limit:
            raise CommandError("Increase --limit to cover the supplied IDs")

        testimony_model = apps.get_model("posts", "Testimony")
        queryset = testimony_model._base_manager.all().order_by("pk")
        if ids:
            queryset = queryset.filter(pk__in=ids)
        else:
            queryset = queryset.filter(type="video", is_converted=True)

        apply = bool(options["apply"])
        self.stdout.write(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
        self.stdout.write(f"Storage: {default_storage.__class__.__name__}")

        eligible = succeeded = skipped = failed = 0
        seen_ids: set[int] = set()

        for obj in queryset.iterator(chunk_size=100):
            seen_ids.add(obj.pk)
            video = self._eligible_video(obj)
            if video is None:
                skipped += 1
                continue
            if eligible >= limit:
                break
            eligible += 1
            try:
                playlist = self._choose_playlist(video)
                master_key = safe_storage_key(video["key"])
                segments = select_hls_segments(
                    storage=default_storage,
                    master_key=master_key,
                    quality_playlist_key=playlist,
                    seconds=PREVIEW_SECONDS,
                )
                if not all(default_storage.exists(s.key) for s in segments):
                    raise HLSPreviewSourceError("Required HLS segment missing")

                self.stdout.write(
                    f"Testimony {obj.pk}: HLS source OK; segments={len(segments)}"
                )
                if not apply:
                    continue

                result = self._generate_and_bind(
                    model=testimony_model,
                    object_id=obj.pk,
                    expected_master=master_key,
                    segments=segments,
                )
                if result == "updated":
                    succeeded += 1
                    self.stdout.write(self.style.SUCCESS(f"Testimony {obj.pk}: preview stored"))
                else:
                    skipped += 1
                    self.stdout.write(f"Testimony {obj.pk}: not changed ({result})")
            except Exception as exc:
                failed += 1
                logger.exception("Testimony %s preview backfill failed", obj.pk)
                self.stderr.write(self.style.ERROR(
                    f"Testimony {obj.pk}: {type(exc).__name__}: {exc}"
                ))

        if ids:
            missing = sorted(set(ids) - seen_ids)
            for object_id in missing:
                failed += 1
                self.stderr.write(self.style.ERROR(f"Testimony {object_id}: does not exist"))

        self.stdout.write(
            f"Summary: eligible={eligible}, updated={succeeded}, "
            f"skipped={skipped}, failed={failed}, mode={'apply' if apply else 'dry-run'}"
        )
        if failed:
            raise CommandError(f"{failed} testimonies could not be processed")

    @staticmethod
    def _eligible_video(obj) -> dict | None:
        if getattr(obj, "type", None) != "video":
            return None
        if not getattr(obj, "is_converted", False):
            return None
        assets = getattr(obj, "media_assets", None)
        if not isinstance(assets, dict):
            return None
        video = assets.get("video")
        if not isinstance(video, dict) or not video.get("key"):
            return None
        preview = video.get("preview")
        if isinstance(preview, dict) and preview.get("key"):
            return None
        return video

    @staticmethod
    def _choose_playlist(video: dict) -> str:
        master = safe_storage_key(video["key"])
        root = posixpath.dirname(master)
        qualities = video.get("qualities")
        if not isinstance(qualities, list):
            raise HLSPreviewSourceError("No video qualities")

        candidates = []
        for quality in qualities:
            if not isinstance(quality, dict):
                continue
            width = quality.get("width")
            if isinstance(width, bool) or not isinstance(width, (float, int)):
                continue
            for field in ("playlist_key", "path", "key"):
                value = quality.get(field)
                if not isinstance(value, str) or not value.endswith(".m3u8"):
                    continue
                try:
                    clean = safe_storage_key(value)
                    for candidate in (clean, posixpath.join(root, clean)):
                        candidate = posixpath.normpath(candidate)
                        if (
                            posixpath.commonpath((root, candidate)) == root
                            and default_storage.exists(candidate)
                        ):
                            candidates.append((
                                0 if width >= PREVIEW_WIDTH else 1,
                                abs(width - PREVIEW_WIDTH),
                                candidate,
                            ))
                except (HLSPreviewSourceError, OSError, ValueError):
                    continue
        if not candidates:
            raise HLSPreviewSourceError("No suitable HLS rendition playlist found")
        return min(candidates)[2]

    @staticmethod
    def _generate_and_bind(*, model, object_id: int, expected_master: str, segments) -> str:
        root = posixpath.dirname(expected_master)
        output_key = posixpath.join(root, f"preview_backfill_{uuid.uuid4().hex}.mp4")
        saved_key = None
        bound = False

        try:
            with tempfile.TemporaryDirectory(prefix="townlit-preview-backfill-") as folder:
                local_source = stage_hls_preview_source(
                    storage=default_storage,
                    segments=segments,
                    directory=folder,
                )
                metadata = build_video_preview_mp4(
                    local_source_path=local_source,
                    output_key=output_key,
                    seconds=PREVIEW_SECONDS,
                    width=PREVIEW_WIDTH,
                )

            if not isinstance(metadata, dict) or not metadata.get("key"):
                raise HLSPreviewSourceError("Generator returned no preview metadata")
            returned_key = safe_storage_key(metadata["key"])
            output_stem = posixpath.basename(output_key).removesuffix(".mp4")
            if (
                posixpath.dirname(returned_key) != root
                or not posixpath.basename(returned_key).startswith(output_stem)
                or not returned_key.endswith(".mp4")
            ):
                raise HLSPreviewSourceError("Generator returned unexpected output key")
            saved_key = returned_key
            if not default_storage.exists(saved_key):
                raise HLSPreviewSourceError("Generated preview not present in storage")
            if not metadata.get("duration_ms") or not metadata.get("width"):
                raise HLSPreviewSourceError("Generated preview metadata incomplete")

            with transaction.atomic():
                locked = model._base_manager.select_for_update().get(pk=object_id)
                video = Command._eligible_video(locked)
                if video is None:
                    return "already updated or no longer eligible"
                if safe_storage_key(video["key"]) != expected_master:
                    return "video changed during processing"

                assets = deepcopy(locked.media_assets)
                assets["video"] = {**video, "preview": metadata}
                # Update only the manifest; keep updated_at, HLS, and thumbnail unchanged.
                updated_rows = model._base_manager.filter(pk=object_id).update(
                    media_assets=assets
                )
                if updated_rows != 1:
                    raise HLSPreviewSourceError("Manifest update did not affect one row")
            bound = True
            return "updated"
        finally:
            if saved_key and not bound:
                # Unique output of this invocation; never delete an old published preview.
                try:
                    default_storage.delete(saved_key)
                except Exception:
                    logger.exception("Orphaned preview cleanup failed for Testimony %s", object_id)

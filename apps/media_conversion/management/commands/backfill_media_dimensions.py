# apps/media_conversion/management/commands/backfill_media_dimensions.py

from __future__ import annotations

import logging
import os
from tempfile import NamedTemporaryFile
from typing import Any

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.posts.models.moment import Moment
from apps.posts.models.pray import Prayer, PrayerResponse
from apps.posts.models.testimony import Testimony

from apps.media_conversion.services.image_variants import build_image_variants
from apps.media_conversion.services.media_metadata import (
    image_metadata_from_storage,
    video_metadata_from_local,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Backfill or force-refresh stored media dimensions, image variants, "
        "and video preview/layout metadata."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            choices=[
                "all",
                "moment",
                "prayer",
                "prayerresponse",
                "testimony",
            ],
            default="all",
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Optional max rows per model. 0 means no limit.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Overwrite existing width/height/aspect_ratio. "
                "Use this after metadata logic changes."
            ),
        )

        parser.add_argument(
            "--include-video",
            action="store_true",
            help=(
                "Refresh media_assets.video dimensions from HLS segments "
                "and preview mp4 when available."
            ),
        )

        parser.add_argument(
            "--rebuild-image-variants",
            action="store_true",
            help=(
                "Build missing image variants from the stored image key. "
                "This improves legacy Square/Profile grid performance."
            ),
        )

    def handle(self, *args, **options):
        model = options["model"]
        limit = int(options["limit"] or 0)
        dry_run = bool(options["dry_run"])
        force = bool(options["force"])
        include_video = bool(options["include_video"])
        rebuild_image_variants = bool(options["rebuild_image_variants"])

        total_updated = 0

        self.stdout.write(
            self.style.WARNING(
                "Backfill started: "
                f"model={model} limit={limit} dry_run={dry_run} "
                f"force={force} include_video={include_video} "
                f"rebuild_image_variants={rebuild_image_variants}"
            )
        )

        if model in {"all", "moment"}:
            total_updated += self.backfill_moments(
                limit=limit,
                dry_run=dry_run,
                force=force,
                include_video=include_video,
                rebuild_image_variants=rebuild_image_variants,
            )

        if model in {"all", "prayer"}:
            total_updated += self.backfill_filefield_model(
                queryset=Prayer.objects.all(),
                model_label="Prayer",
                image_fields=["image", "thumbnail"],
                video_fields=["video"],
                limit=limit,
                dry_run=dry_run,
                force=force,
                include_video=include_video,
                rebuild_image_variants=rebuild_image_variants,
            )

        if model in {"all", "prayerresponse"}:
            total_updated += self.backfill_filefield_model(
                queryset=PrayerResponse.objects.all(),
                model_label="PrayerResponse",
                image_fields=["image", "thumbnail"],
                video_fields=["video"],
                limit=limit,
                dry_run=dry_run,
                force=force,
                include_video=include_video,
                rebuild_image_variants=rebuild_image_variants,
            )

        if model in {"all", "testimony"}:
            total_updated += self.backfill_filefield_model(
                queryset=Testimony.objects.all(),
                model_label="Testimony",
                image_fields=["thumbnail"],
                video_fields=["video"],
                limit=limit,
                dry_run=dry_run,
                force=force,
                include_video=include_video,
                rebuild_image_variants=rebuild_image_variants,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill completed. updated={total_updated} dry_run={dry_run}"
            )
        )

    # ------------------------------------------------------------------
    # Moment
    # ------------------------------------------------------------------

    def backfill_moments(
        self,
        *,
        limit: int,
        dry_run: bool,
        force: bool,
        include_video: bool,
        rebuild_image_variants: bool,
    ) -> int:
        qs = Moment.objects.all().order_by("id")

        if limit > 0:
            qs = qs[:limit]

        updated_count = 0

        for moment in qs.iterator():
            changed = False

            image_items = (
                moment.image_items
                if isinstance(moment.image_items, list)
                else []
            )

            updated_items = image_items

            if image_items:
                updated_items, image_items_changed = self.refresh_moment_image_items(
                    moment=moment,
                    items=image_items,
                    force=force,
                    rebuild_image_variants=rebuild_image_variants,
                )

                changed = changed or image_items_changed

            media_assets = dict(getattr(moment, "media_assets", None) or {})
            media_assets_changed = False

            # Moment legacy image/thumbnail assets, if present.
            media_assets, legacy_image_changed = self.refresh_image_assets(
                obj=moment,
                media_assets=media_assets,
                fields=["image", "thumbnail"],
                force=force,
                rebuild_image_variants=rebuild_image_variants,
            )

            media_assets_changed = media_assets_changed or legacy_image_changed

            if include_video:
                media_assets, video_changed = self.refresh_video_assets(
                    obj=moment,
                    media_assets=media_assets,
                    fields=["video"],
                    force=force,
                )

                media_assets_changed = media_assets_changed or video_changed

            changed = changed or media_assets_changed

            if not changed:
                continue

            updated_count += 1

            self.stdout.write(
                f"[Moment:{moment.pk}] media metadata refreshed"
            )

            if dry_run:
                continue

            update_payload = {}

            if updated_items is not image_items:
                update_payload["image_items"] = updated_items

            if media_assets_changed:
                update_payload["media_assets"] = media_assets

            if not update_payload:
                continue

            with transaction.atomic():
                Moment.objects.filter(pk=moment.pk).update(
                    **update_payload,
                )

        return updated_count

    def refresh_moment_image_items(
        self,
        *,
        moment: Moment,
        items: list[dict],
        force: bool,
        rebuild_image_variants: bool,
    ) -> tuple[list[dict], bool]:
        changed = False
        updated_items = []

        for item in items:
            if not isinstance(item, dict):
                updated_items.append(item)
                continue

            key = self.clean_key(item.get("key"))

            if not key:
                updated_items.append(item)
                continue

            should_refresh_dimensions = force or not self.has_dimensions(item)

            metadata = None

            if should_refresh_dimensions:
                metadata = self.safe_image_metadata(key)

            variants = item.get("variants")
            variants = variants if isinstance(variants, dict) else {}

            if rebuild_image_variants and key:
                rebuilt_variants = self.safe_build_image_variants(
                    source_key=key,
                    owner_label=f"moment-{moment.pk}-item-{item.get('id') or 'image'}",
                )

                if rebuilt_variants:
                    variants = rebuilt_variants
                    changed = True

            refreshed_variants, variants_changed = self.refresh_image_variant_metadata(
                variants=variants,
                force=force,
            )

            if variants_changed:
                variants = refreshed_variants
                changed = True

            updated_item = dict(item)

            if metadata:
                updated_item.update(
                    {
                        "width": metadata.get("width"),
                        "height": metadata.get("height"),
                        "aspect_ratio": metadata.get("aspect_ratio"),
                        "mime_type": metadata.get("mime_type") or item.get("mime_type") or "image/jpeg",
                        "size": metadata.get("size") or item.get("size") or 0,
                    }
                )
                changed = True

            if variants:
                updated_item["variants"] = variants

            updated_items.append(updated_item)

        return updated_items, changed

    # ------------------------------------------------------------------
    # FileField-backed models
    # ------------------------------------------------------------------

    def backfill_filefield_model(
        self,
        *,
        queryset,
        model_label: str,
        image_fields: list[str],
        video_fields: list[str],
        limit: int,
        dry_run: bool,
        force: bool,
        include_video: bool,
        rebuild_image_variants: bool,
    ) -> int:
        qs = queryset.order_by("id")

        if limit > 0:
            qs = qs[:limit]

        updated_count = 0

        for obj in qs.iterator():
            if not hasattr(obj, "media_assets"):
                continue

            media_assets = dict(getattr(obj, "media_assets", None) or {})
            changed = False

            media_assets, image_changed = self.refresh_image_assets(
                obj=obj,
                media_assets=media_assets,
                fields=image_fields,
                force=force,
                rebuild_image_variants=rebuild_image_variants,
            )

            changed = changed or image_changed

            if include_video:
                media_assets, video_changed = self.refresh_video_assets(
                    obj=obj,
                    media_assets=media_assets,
                    fields=video_fields,
                    force=force,
                )

                changed = changed or video_changed

            if not changed:
                continue

            updated_count += 1

            self.stdout.write(
                f"[{model_label}:{obj.pk}] media_assets refreshed"
            )

            if dry_run:
                continue

            type(obj).objects.filter(pk=obj.pk).update(
                media_assets=media_assets,
            )

        return updated_count

    # ------------------------------------------------------------------
    # Image assets
    # ------------------------------------------------------------------

    def refresh_image_assets(
        self,
        *,
        obj,
        media_assets: dict,
        fields: list[str],
        force: bool,
        rebuild_image_variants: bool,
    ) -> tuple[dict, bool]:
        changed = False

        for field_name in fields:
            file_value = getattr(obj, field_name, None)
            key = self.clean_key(file_value)

            existing = media_assets.get(field_name)
            existing = existing if isinstance(existing, dict) else {}

            if not key:
                key = self.clean_key(existing.get("key"))

            if not key:
                continue

            should_refresh_dimensions = force or not self.has_dimensions(existing)

            metadata = None

            if should_refresh_dimensions:
                metadata = self.safe_image_metadata(key)

            variants = existing.get("variants")
            variants = variants if isinstance(variants, dict) else {}

            if rebuild_image_variants:
                rebuilt_variants = self.safe_build_image_variants(
                    source_key=key,
                    owner_label=f"{obj._meta.model_name}-{obj.pk}-{field_name}",
                )

                if rebuilt_variants:
                    variants = rebuilt_variants
                    changed = True

            refreshed_variants, variants_changed = self.refresh_image_variant_metadata(
                variants=variants,
                force=force,
            )

            if variants_changed:
                variants = refreshed_variants
                changed = True

            if not metadata and not variants_changed and not rebuild_image_variants:
                continue

            payload = dict(existing)

            if metadata:
                payload.update(
                    {
                        "key": key,
                        "mime_type": metadata.get("mime_type") or "image/jpeg",
                        "size": metadata.get("size") or existing.get("size") or 0,
                        "width": metadata.get("width"),
                        "height": metadata.get("height"),
                        "aspect_ratio": metadata.get("aspect_ratio"),
                    }
                )
                changed = True

            if variants:
                payload["variants"] = variants

            media_assets[field_name] = self.clean_payload(payload)

        return media_assets, changed

    def refresh_image_variant_metadata(
        self,
        *,
        variants: dict,
        force: bool,
    ) -> tuple[dict, bool]:
        if not isinstance(variants, dict) or not variants:
            return variants or {}, False

        changed = False
        refreshed = {}

        for name, payload in variants.items():
            if not isinstance(payload, dict):
                refreshed[name] = payload
                continue

            key = self.clean_key(payload.get("key"))

            if not key:
                refreshed[name] = payload
                continue

            if not force and self.has_dimensions(payload):
                refreshed[name] = payload
                continue

            metadata = self.safe_image_metadata(key)

            if not metadata:
                refreshed[name] = payload
                continue

            refreshed[name] = self.clean_payload(
                {
                    **payload,
                    "key": key,
                    "mime_type": metadata.get("mime_type") or "image/jpeg",
                    "size": metadata.get("size") or payload.get("size") or 0,
                    "width": metadata.get("width"),
                    "height": metadata.get("height"),
                    "aspect_ratio": metadata.get("aspect_ratio"),
                }
            )

            changed = True

        return refreshed, changed

    def safe_build_image_variants(
        self,
        *,
        source_key: str,
        owner_label: str,
    ) -> dict | None:
        key = self.clean_key(source_key)

        if not key:
            return None

        try:
            if not default_storage.exists(key):
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing image source for variants: {key}"
                    )
                )
                return None

            source_dir = os.path.dirname(key)
            source_base = os.path.splitext(os.path.basename(key))[0]

            variants = build_image_variants(
                source_key=key,
                base_output_dir=f"{source_dir}/variants",
                basename=f"{source_base}_{owner_label}",
            )

            return variants or None

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"Could not build image variants for {key}: {exc}"
                )
            )
            return None

    # ------------------------------------------------------------------
    # Video assets
    # ------------------------------------------------------------------

    def refresh_video_assets(
        self,
        *,
        obj,
        media_assets: dict,
        fields: list[str],
        force: bool,
    ) -> tuple[dict, bool]:

        changed = False

        for field_name in fields:
            file_value = getattr(obj, field_name, None)
            field_key = self.clean_key(file_value)

            existing = media_assets.get(field_name)
            existing = existing if isinstance(existing, dict) else {}

            video_key = field_key or self.clean_key(existing.get("key"))

            if not video_key:
                continue

            payload = dict(existing)
            payload["key"] = video_key

            qualities = payload.get("qualities")
            qualities = qualities if isinstance(qualities, list) else []

            if not qualities:
                inferred_qualities = self.infer_hls_qualities_from_master(
                    master_key=video_key,
                )

                if inferred_qualities:
                    qualities = inferred_qualities
                    payload["qualities"] = qualities
                    changed = True

            refreshed_qualities, qualities_changed = self.refresh_hls_quality_metadata(
                master_key=video_key,
                qualities=qualities,
                force=force,
            )

            if qualities_changed:
                payload["qualities"] = refreshed_qualities
                changed = True

            source_quality = self.find_source_quality(refreshed_qualities)

            should_refresh_video = force or not self.has_dimensions(payload)

            if should_refresh_video and source_quality and self.has_dimensions(source_quality):
                payload.update(
                    {
                        "width": source_quality.get("width"),
                        "height": source_quality.get("height"),
                        "aspect_ratio": source_quality.get("aspect_ratio"),
                    }
                )
                changed = True

            if not payload.get("duration_ms") and source_quality:
                playlist_key = self.quality_playlist_key(
                    master_key=video_key,
                    quality=source_quality,
                )

                duration_ms = self.hls_playlist_duration_ms(
                    playlist_key=playlist_key,
                )

                if duration_ms:
                    payload["duration_ms"] = duration_ms
                    changed = True

            preview = payload.get("preview")
            if isinstance(preview, dict):
                refreshed_preview, preview_changed = self.refresh_video_preview_metadata(
                    preview=preview,
                    force=force,
                )

                if preview_changed:
                    payload["preview"] = refreshed_preview
                    changed = True

            media_assets[field_name] = self.clean_payload(payload)

        return media_assets, changed

    def refresh_hls_quality_metadata(
        self,
        *,
        master_key: str,
        qualities: list,
        force: bool,
    ) -> tuple[list, bool]:
        master_key = self.clean_key(master_key)

        if not master_key:
            return qualities or [], False

        qualities = qualities if isinstance(qualities, list) else []

        if not qualities:
            qualities = self.infer_hls_qualities_from_master(
                master_key=master_key,
            )

            if not qualities:
                return [], False

        changed = False
        refreshed = []

        for quality in qualities:
            if not isinstance(quality, dict):
                refreshed.append(quality)
                continue

            if not force and self.has_dimensions(quality):
                refreshed.append(quality)
                continue

            playlist_key = self.quality_playlist_key(
                master_key=master_key,
                quality=quality,
            )

            if not playlist_key:
                refreshed.append(quality)
                continue

            segment_key = self.first_hls_segment_key(
                playlist_key=playlist_key,
            )

            if not segment_key:
                refreshed.append(quality)
                continue

            metadata = self.safe_video_metadata_from_storage_key(
                segment_key,
            )

            if not metadata or not self.has_dimensions(metadata):
                refreshed.append(quality)
                continue

            refreshed_quality = self.clean_payload(
                {
                    **quality,
                    "width": metadata.get("width"),
                    "height": metadata.get("height"),
                    "aspect_ratio": metadata.get("aspect_ratio"),
                }
            )

            refreshed.append(refreshed_quality)
            changed = True

        return refreshed, changed

    def refresh_video_preview_metadata(
        self,
        *,
        preview: dict,
        force: bool,
    ) -> tuple[dict, bool]:
        key = self.clean_key(preview.get("key"))

        if not key:
            return preview, False

        if not force and self.has_dimensions(preview):
            return preview, False

        metadata = self.safe_video_metadata_from_storage_key(key)

        if not metadata or not self.has_dimensions(metadata):
            return preview, False

        refreshed = self.clean_payload(
            {
                **preview,
                "key": key,
                "mime_type": preview.get("mime_type") or "video/mp4",
                "size": self.safe_storage_size(key) or preview.get("size") or 0,
                "width": metadata.get("width"),
                "height": metadata.get("height"),
                "aspect_ratio": metadata.get("aspect_ratio"),
                "duration_ms": metadata.get("duration_ms") or preview.get("duration_ms"),
            }
        )

        return refreshed, True

    def quality_playlist_key(
        self,
        *,
        master_key: str,
        quality: dict,
    ) -> str | None:
        base_dir = os.path.dirname(master_key)

        raw_path = (
            quality.get("path")
            or quality.get("url")
            or quality.get("key")
        )

        path = self.clean_key(raw_path)

        if not path:
            return None

        # Existing qualities usually store "source/playlist.m3u8".
        if path.endswith(".m3u8") and not path.startswith(base_dir):
            return self.clean_key(os.path.join(base_dir, path))

        return path

    def first_hls_segment_key(
        self,
        *,
        playlist_key: str,
    ) -> str | None:
        playlist_key = self.clean_key(playlist_key)

        if not playlist_key:
            return None

        try:
            if not default_storage.exists(playlist_key):
                return None

            with default_storage.open(playlist_key, "rb") as file:
                content = file.read().decode("utf-8", "ignore")

            base_dir = os.path.dirname(playlist_key)

            for raw_line in content.splitlines():
                line = raw_line.strip()

                if not line or line.startswith("#"):
                    continue

                if line.startswith("http://") or line.startswith("https://"):
                    # This command intentionally supports storage keys only.
                    continue

                if line.endswith(".ts") or ".ts" in line:
                    return self.clean_key(os.path.join(base_dir, line))

            return None

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"Could not inspect HLS playlist {playlist_key}: {exc}"
                )
            )
            return None

    def find_source_quality(
        self,
        qualities: list,
    ) -> dict | None:
        if not qualities:
            return None

        for quality in qualities:
            if isinstance(quality, dict) and quality.get("key") == "source":
                return quality

        for quality in qualities:
            if isinstance(quality, dict) and self.has_dimensions(quality):
                return quality

        return None

    def infer_hls_qualities_from_master(
        self,
        *,
        master_key: str,
    ) -> list:
        master_key = self.clean_key(master_key)

        if not master_key:
            return []

        try:
            if not default_storage.exists(master_key):
                return []

            with default_storage.open(master_key, "rb") as file:
                content = file.read().decode("utf-8", "ignore")

            base_dir = os.path.dirname(master_key)
            qualities = []
            pending_bandwidth = None
            pending_resolution = None

            for raw_line in content.splitlines():
                line = raw_line.strip()

                if not line:
                    continue

                if line.startswith("#EXT-X-STREAM-INF"):
                    pending_bandwidth = self.extract_m3u8_attribute(
                        line,
                        "BANDWIDTH",
                    )
                    pending_resolution = self.extract_m3u8_attribute(
                        line,
                        "RESOLUTION",
                    )
                    continue

                if line.startswith("#"):
                    continue

                if not line.endswith(".m3u8"):
                    continue

                path = line
                playlist_key = self.clean_key(os.path.join(base_dir, path))

                width = None
                height = None
                aspect_ratio = None

                if pending_resolution and "x" in pending_resolution:
                    try:
                        raw_width, raw_height = pending_resolution.lower().split("x", 1)
                        width = int(raw_width)
                        height = int(raw_height)
                        aspect_ratio = width / height if width and height else None
                    except Exception:
                        width = None
                        height = None
                        aspect_ratio = None

                quality_key = "source" if not qualities else f"q{len(qualities) + 1}"

                qualities.append(
                    self.clean_payload(
                        {
                            "key": quality_key,
                            "path": path,
                            "playlist_key": playlist_key,
                            "width": width,
                            "height": height,
                            "bandwidth": pending_bandwidth,
                            "aspect_ratio": aspect_ratio,
                        }
                    )
                )

                pending_bandwidth = None
                pending_resolution = None

            return qualities

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"Could not infer HLS qualities from {master_key}: {exc}"
                )
            )
            return []

    def extract_m3u8_attribute(
        self,
        line: str,
        name: str,
    ) -> str | None:
        marker = f"{name}="

        if marker not in line:
            return None

        try:
            value = line.split(marker, 1)[1].split(",", 1)[0].strip()
            return value.strip('"') or None
        except Exception:
            return None

    def hls_playlist_duration_ms(
        self,
        *,
        playlist_key: str,
    ) -> int | None:
        playlist_key = self.clean_key(playlist_key)

        if not playlist_key:
            return None

        try:
            if not default_storage.exists(playlist_key):
                return None

            with default_storage.open(playlist_key, "rb") as file:
                content = file.read().decode("utf-8", "ignore")

            total_seconds = 0.0

            for raw_line in content.splitlines():
                line = raw_line.strip()

                if not line.startswith("#EXTINF:"):
                    continue

                try:
                    value = line.split(":", 1)[1].split(",", 1)[0]
                    total_seconds += float(value)
                except Exception:
                    continue

            if total_seconds <= 0:
                return None

            return int(total_seconds * 1000)

        except Exception:
            return None
        
    # ------------------------------------------------------------------
    # Storage metadata helpers
    # ------------------------------------------------------------------

    def safe_image_metadata(
        self,
        key: str,
    ) -> dict | None:
        key = self.clean_key(key)

        if not key:
            return None

        try:
            if not default_storage.exists(key):
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing image storage key: {key}"
                    )
                )
                return None

            metadata = image_metadata_from_storage(key)

            if not self.has_dimensions(metadata):
                return None

            return metadata

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"Could not read image metadata for {key}: {exc}"
                )
            )
            return None

    def safe_video_metadata_from_storage_key(
        self,
        key: str,
    ) -> dict | None:
        key = self.clean_key(key)

        if not key:
            return None

        local_path = None

        try:
            if not default_storage.exists(key):
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing video storage key: {key}"
                    )
                )
                return None

            suffix = os.path.splitext(key)[1] or ".video"

            with default_storage.open(key, "rb") as source:
                with NamedTemporaryFile(
                    delete=False,
                    suffix=suffix,
                ) as temp:
                    temp.write(source.read())
                    temp.flush()
                    local_path = temp.name

            metadata = video_metadata_from_local(local_path)

            if not self.has_dimensions(metadata):
                return None

            return metadata

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"Could not read video metadata for {key}: {exc}"
                )
            )
            return None

        finally:
            try:
                if local_path and os.path.exists(local_path):
                    os.remove(local_path)
            except Exception:
                pass

    def safe_storage_size(
        self,
        key: str,
    ) -> int:
        key = self.clean_key(key)

        if not key:
            return 0

        try:
            if default_storage.exists(key):
                return int(default_storage.size(key) or 0)
        except Exception:
            pass

        return 0

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def clean_key(
        self,
        value,
    ) -> str | None:
        if not value:
            return None

        raw = getattr(value, "name", value)

        if not raw:
            return None

        cleaned = str(raw).strip().lstrip("/")
        return cleaned or None

    def has_dimensions(
        self,
        payload: dict,
    ) -> bool:
        if not isinstance(payload, dict):
            return False

        return bool(
            payload.get("width")
            and payload.get("height")
            and payload.get("aspect_ratio")
        )

    def clean_payload(
        self,
        payload: dict,
    ) -> dict:
        return {
            key: value
            for key, value in (payload or {}).items()
            if value is not None
        }
        
        
        
# docker compose exec backend python manage.py backfill_media_dimensions --model all --limit 20 --force --include-video --dry-run
# docker compose exec backend python manage.py backfill_media_dimensions --model all --force --include-video
# docker compose exec backend python manage.py backfill_media_dimensions --model all --force --include-video --rebuild-image-variants
# docker compose exec backend python manage.py backfill_media_dimensions --model testimony --force --include-video
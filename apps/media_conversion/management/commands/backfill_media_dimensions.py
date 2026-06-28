# apps/media_conversion/management/commands/backfill_media_dimensions.py

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.db import transaction

from apps.posts.models.moment import Moment
from apps.posts.models.pray import Prayer, PrayerResponse
from apps.posts.models.testimony import Testimony

from apps.media_conversion.services.media_metadata import (
    image_metadata_from_storage,
    video_metadata_from_storage,
)


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill stored media dimensions for legacy image/video previews."

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            choices=[
                "all",
                "moment",
                "prayer",
                "prayerresponse",
                "testimony",
                "testimonyvideo",
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

    def handle(self, *args, **options):
        model = options["model"]
        limit = int(options["limit"] or 0)
        dry_run = bool(options["dry_run"])

        total_updated = 0

        if model in {"all", "moment"}:
            total_updated += self.backfill_moments(
                limit=limit,
                dry_run=dry_run,
            )

        if model in {"all", "prayer"}:
            total_updated += self.backfill_image_filefield_model(
                queryset=Prayer.objects.all(),
                model_label="Prayer",
                fields=["image", "thumbnail"],
                limit=limit,
                dry_run=dry_run,
            )

        if model in {"all", "prayerresponse"}:
            total_updated += self.backfill_image_filefield_model(
                queryset=PrayerResponse.objects.all(),
                model_label="PrayerResponse",
                fields=["image", "thumbnail"],
                limit=limit,
                dry_run=dry_run,
            )

        if model in {"all", "testimony"}:
            total_updated += self.backfill_image_filefield_model(
                queryset=Testimony.objects.all(),
                model_label="Testimony",
                fields=["thumbnail"],
                limit=limit,
                dry_run=dry_run,
            )

            total_updated += self.backfill_video_filefield_model(
                queryset=Testimony.objects.all(),
                model_label="Testimony",
                fields=["video"],
                limit=limit,
                dry_run=dry_run,
            )

        if model == "testimonyvideo":
            total_updated += self.backfill_video_filefield_model(
                queryset=Testimony.objects.all(),
                model_label="Testimony",
                fields=["video"],
                limit=limit,
                dry_run=dry_run,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill completed. updated={total_updated} dry_run={dry_run}"
            )
        )

    # MARK: - Moment image_items

    def backfill_moments(
        self,
        *,
        limit: int,
        dry_run: bool,
    ) -> int:
        qs = (
            Moment.objects
            .exclude(image_items=[])
            .order_by("id")
        )

        if limit > 0:
            qs = qs[:limit]

        updated_count = 0

        for moment in qs.iterator():
            items = moment.image_items if isinstance(moment.image_items, list) else []
            if not items:
                continue

            changed = False
            updated_items = []

            for item in items:
                if not isinstance(item, dict):
                    continue

                key = self.clean_key(item.get("key"))
                if not key:
                    updated_items.append(item)
                    continue

                if self.has_image_dimensions(item):
                    updated_items.append(item)
                    continue

                metadata = self.safe_image_metadata(key)
                if not metadata:
                    updated_items.append(item)
                    continue

                updated_item = {
                    **item,
                    "width": metadata.get("width"),
                    "height": metadata.get("height"),
                    "aspect_ratio": metadata.get("aspect_ratio"),
                }

                updated_items.append(updated_item)
                changed = True

            if not changed:
                continue

            updated_count += 1

            self.stdout.write(
                f"[Moment:{moment.pk}] image_items dimensions updated"
            )

            if dry_run:
                continue

            with transaction.atomic():
                Moment.objects.filter(pk=moment.pk).update(
                    image_items=updated_items,
                )

        return updated_count

    # MARK: - FileField-backed image models

    def backfill_image_filefield_model(
        self,
        *,
        queryset,
        model_label: str,
        fields: list[str],
        limit: int,
        dry_run: bool,
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

            for field_name in fields:
                if not hasattr(obj, field_name):
                    continue

                file_value = getattr(obj, field_name, None)
                key = self.clean_key(file_value)

                if not key:
                    continue

                existing = media_assets.get(field_name)
                if isinstance(existing, dict) and self.has_image_dimensions(existing):
                    continue

                metadata = self.safe_image_metadata(key)
                if not metadata:
                    continue

                media_assets[field_name] = {
                    **(existing if isinstance(existing, dict) else {}),
                    "key": key,
                    "mime_type": metadata.get("mime_type") or "image/jpeg",
                    "size": metadata.get("size") or 0,
                    "width": metadata.get("width"),
                    "height": metadata.get("height"),
                    "aspect_ratio": metadata.get("aspect_ratio"),
                }

                changed = True

            if not changed:
                continue

            updated_count += 1

            self.stdout.write(
                f"[{model_label}:{obj.pk}] media_assets image dimensions updated"
            )

            if dry_run:
                continue

            type(obj).objects.filter(pk=obj.pk).update(
                media_assets=media_assets,
            )

        return updated_count

    # MARK: - FileField-backed video models

    def backfill_video_filefield_model(
        self,
        *,
        queryset,
        model_label: str,
        fields: list[str],
        limit: int,
        dry_run: bool,
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

            for field_name in fields:
                if not hasattr(obj, field_name):
                    continue

                file_value = getattr(obj, field_name, None)
                key = self.clean_key(file_value)

                if not key:
                    continue

                existing = media_assets.get(field_name)
                if isinstance(existing, dict) and self.has_video_metadata(existing):
                    continue

                metadata = self.safe_video_metadata(key)
                if not metadata:
                    continue

                media_assets[field_name] = {
                    **(existing if isinstance(existing, dict) else {}),
                    "key": key,
                    "mime_type": metadata.get("mime_type") or "video/mp4",
                    "size": metadata.get("size") or 0,
                    "width": metadata.get("width"),
                    "height": metadata.get("height"),
                    "aspect_ratio": metadata.get("aspect_ratio"),
                    "duration_ms": metadata.get("duration_ms"),
                    "duration_seconds": metadata.get("duration_seconds"),
                }

                changed = True

            if not changed:
                continue

            updated_count += 1

            self.stdout.write(
                f"[{model_label}:{obj.pk}] media_assets video metadata updated"
            )

            if dry_run:
                continue

            type(obj).objects.filter(pk=obj.pk).update(
                media_assets=media_assets,
            )

        return updated_count

    # MARK: - Helpers

    def clean_key(self, value) -> str | None:
        if not value:
            return None

        raw = getattr(value, "name", value)

        if not raw:
            return None

        cleaned = str(raw).strip().lstrip("/")
        return cleaned or None

    def has_image_dimensions(self, payload: dict) -> bool:
        return bool(
            payload.get("width")
            and payload.get("height")
            and payload.get("aspect_ratio")
        )

    def has_video_metadata(self, payload: dict) -> bool:
        return bool(
            payload.get("width")
            and payload.get("height")
            and payload.get("aspect_ratio")
            and payload.get("duration_ms")
        )

    def safe_image_metadata(self, key: str) -> dict | None:
        key = self.clean_key(key)

        if not key:
            return None

        try:
            if not default_storage.exists(key):
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing storage key: {key}"
                    )
                )
                return None

            metadata = image_metadata_from_storage(key)

            if not self.has_image_dimensions(metadata):
                return None

            return metadata

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"Could not read image metadata for {key}: {exc}"
                )
            )
            return None

    def safe_video_metadata(self, key: str) -> dict | None:
        key = self.clean_key(key)

        if not key:
            return None

        try:
            if not default_storage.exists(key):
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing storage key: {key}"
                    )
                )
                return None

            metadata = video_metadata_from_storage(key)

            if not self.has_video_metadata(metadata):
                return None

            return metadata

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"Could not read video metadata for {key}: {exc}"
                )
            )
            return None
        
# docker compose exec backend python manage.py backfill_media_dimensions --model all
# docker compose exec backend python manage.py backfill_media_dimensions --model moment
# docker compose exec backend python manage.py backfill_media_dimensions --model prayer
# docker compose exec backend python manage.py backfill_media_dimensions --model prayerresponse
# docker compose exec backend python manage.py backfill_media_dimensions --model testimony
# docker compose exec backend python manage.py backfill_media_dimensions --model testimonyvideo
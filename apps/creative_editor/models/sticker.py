# apps/creative_editor/models/sticker.py

from __future__ import annotations

from django.db import models
from django.db.models import Q

from utils.common.utils import FileUpload
from utils.mixins.media_assets import MediaAssetsMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin
from utils.mixins.media_conversion import MediaConversionMixin
from utils.mixins.slug_mixin import SlugMixin
from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.security_validators import validate_no_executable_file

from .base import PublicIDTimestampedModel


class StickerPack(
    SlugMixin,
    PublicIDTimestampedModel,
):
    """
    A curated collection of stickers.
    """

    SLUG_ALLOW_UNICODE = False

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    cover_color = models.CharField(
        max_length=16,
        blank=True,
        default="",
    )
    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    def get_slug_source(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Sticker Pack"
        verbose_name_plural = "Sticker Packs"
        ordering = ("sort_order", "name", "id")

        indexes = [
            models.Index(
                fields=("is_active", "is_featured", "sort_order"),
                name="sticker_pack_active_idx",
            ),
        ]


class StickerAsset(
    MediaAssetsMixin,
    MediaAutoConvertMixin,
    MediaConversionMixin,
    SlugMixin,
    PublicIDTimestampedModel,
):
    """
    A static sticker approved for editor usage.
    """

    SLUG_ALLOW_UNICODE = False

    IMAGE = FileUpload(
        "creative_editor",
        "stickers",
        "assets",
    )

    pack = models.ForeignKey(
        StickerPack,
        on_delete=models.CASCADE,
        related_name="stickers",
    )
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(
        upload_to=IMAGE.dir_upload,
        max_length=700,
        validators=[
            validate_image_file,
            validate_image_size,
            validate_no_executable_file,
        ],
    )
    is_converted = models.BooleanField(default=False, db_index=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    aspect_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=5,
        null=True,
        blank=True,
    )
    dominant_color = models.CharField(
        max_length=16,
        blank=True,
        default="",
    )
    blurhash = models.CharField(
        max_length=180,
        blank=True,
        default="",
    )
    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    media_conversion_config = {
        "image": {
            "upload": IMAGE,
            "kind": "image",
        },
    }

    def _enqueue_conversion_tasks(self):
        """
        Enqueue alpha-preserving sticker conversion.
        """

        from apps.creative_editor.tasks.sticker import (
            convert_sticker_to_png_task,
        )
        from apps.media_conversion.models import MediaJobStatus
        from apps.media_conversion.services.jobs import upsert_job

        if self.is_converted:
            return

        source_path = getattr(self.image, "name", None)

        if not source_path:
            return

        field_name = "image"
        kind = "image"

        if self._should_skip_duplicate_enqueue(
            field_name,
            kind,
            source_path,
        ):
            return

        if not self._acquire_enqueue_lock(
            field_name,
            kind,
            source_path,
        ):
            return

        job = upsert_job(
            instance=self,
            field_name=field_name,
            kind=kind,
            status=MediaJobStatus.QUEUED,
            source_path=source_path,
            message="Queued for sticker processing",
        )

        self._dispatch_conversion_task(
            job=job,
            task=convert_sticker_to_png_task,
            queue="video",
            task_kwargs={
                "model_name": self.__class__.__name__,
                "app_label": self._meta.app_label,
                "instance_id": self.pk,
                "field_name": field_name,
                "source_path": source_path,
                "fileupload": self.IMAGE.to_dict(),
            },
        )

    def get_slug_source(self) -> str:
        return f"{self.pack.name} {self.title}"

    def is_available(self) -> bool:
        return bool(
            self.image
            and self.is_active
            and self.pack.is_active
            and self.is_converted
        )

    def can_deliver_asset(
        self,
        *,
        viewer,
        field_name: str,
        intent: str,
    ) -> bool:
        """
        Deliver approved stickers to authenticated users.
        """

        if (
            viewer is None
            or not getattr(viewer, "is_authenticated", False)
        ):
            return False

        if field_name != "image":
            return False

        return self.is_available()

    def __str__(self) -> str:
        return f"{self.pack.name} · {self.title}"

    class Meta:
        verbose_name = "Sticker Asset"
        verbose_name_plural = "Sticker Assets"
        ordering = ("sort_order", "title", "id")

        indexes = [
            models.Index(
                fields=("pack", "is_active", "sort_order"),
                name="sticker_asset_pack_idx",
            ),
            models.Index(
                fields=("is_featured", "is_active"),
                name="sticker_asset_feature_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=("pack", "title"),
                name="creative_unique_sticker_title_pack",
            ),
            models.CheckConstraint(
                check=Q(width__isnull=True) | Q(width__gt=0),
                name="creative_sticker_width_valid",
            ),
            models.CheckConstraint(
                check=Q(height__isnull=True) | Q(height__gt=0),
                name="creative_sticker_height_valid",
            ),
        ]
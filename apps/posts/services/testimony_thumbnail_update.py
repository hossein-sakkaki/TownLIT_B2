# apps/posts/services/testimony_thumbnail_update.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-02.
# Last Update by Hossein Sakkaki on 2026-11-02.

from __future__ import annotations

import logging
import os

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from apps.media_conversion.services.image_variants import build_image_variants
from apps.media_conversion.services.media_manifest import build_asset_payload
from apps.media_conversion.services.media_metadata import image_metadata_from_storage
from apps.posts.models.testimony import Testimony
from utils.common.image_utils import convert_image_to_jpg

logger = logging.getLogger(__name__)


class ThumbnailUpdateError(Exception):
    """The new thumbnail could not be prepared or published."""


class ThumbnailUpdateConflict(ThumbnailUpdateError):
    """Another request changed this thumbnail during preparation."""


def _key(value) -> str:
    return str(value or "").strip().lstrip("/")


def _delete_prepared(key: str, *, protected_keys: set[str]) -> None:
    key = _key(key)
    if not key or key in protected_keys:
        return
    try:
        default_storage.delete(key)
    except Exception:
        logger.warning("Thumbnail preparation cleanup failed: %s", key, exc_info=True)


def update_testimony_thumbnail(*, obj: Testimony, uploaded) -> Testimony:
    """
    Prepare a new image fully before publishing the FileField and manifest.

    Storage is not transactional. Published keys are never deleted here: old
    signed URLs and in-flight downloads may still reference their objects.
    Old-version garbage collection requires a separate retention policy.
    """
    original_key = _key(getattr(obj.thumbnail, "name", None))
    raw_key = ""
    final_key = ""
    variant_keys: set[str] = set()
    published = False

    try:
        uploaded.seek(0)
        field = Testimony._meta.get_field("thumbnail")
        upload_path = field.generate_filename(obj, uploaded.name)
        raw_key = _key(default_storage.save(_key(upload_path), uploaded))
        if not raw_key:
            raise ThumbnailUpdateError("Thumbnail upload could not be stored.")

        final_key = _key(
            convert_image_to_jpg(
                source_path=raw_key,
                instance=obj,
                fileupload=Testimony.THUMBNAIL,
            )
        )
        if not final_key:
            raise ThumbnailUpdateError("Thumbnail normalization failed.")
        if final_key == original_key:
            raise ThumbnailUpdateError("Thumbnail normalization reused the published key.")

        metadata = image_metadata_from_storage(final_key)
        directory = os.path.dirname(final_key)
        basename = os.path.splitext(os.path.basename(final_key))[0]
        variants = build_image_variants(
            source_key=final_key,
            base_output_dir=f"{directory}/variants",
            basename=basename,
        )
        variant_keys = {
            _key(item.get("key"))
            for item in variants.values()
            if isinstance(item, dict) and item.get("key")
        }
        if not all(name in variants for name in ("thumb", "grid", "feed", "detail")):
            raise ThumbnailUpdateError("Required thumbnail variants are incomplete.")

        manifest = build_asset_payload(
            key=final_key,
            metadata=metadata,
            variants=variants,
            extra={"mime_type": "image/jpeg"},
        )

        with transaction.atomic():
            locked = Testimony.objects.select_for_update().get(pk=obj.pk)
            actual_key = _key(getattr(locked.thumbnail, "name", None))
            if actual_key != original_key:
                raise ThumbnailUpdateConflict("Thumbnail was changed by another request.")
            if locked.type != Testimony.TYPE_VIDEO:
                raise ThumbnailUpdateConflict("Testimony type changed during upload.")

            assets = dict(locked.media_assets or {})
            assets["thumbnail"] = manifest
            # Preserve the model's existing save/signal integration while
            # bypassing only media auto-conversion for this prepared image.
            locked.thumbnail.name = final_key
            locked.media_assets = assets
            locked.updated_at = timezone.now()
            locked._skip_media_autoconvert_once = True
            locked.save(
                update_fields=["thumbnail", "media_assets", "updated_at"]
            )

        published = True
        logger.info("Testimony thumbnail published: id=%s key=%s", obj.pk, final_key)
        return Testimony.objects.get(pk=obj.pk)
    except ThumbnailUpdateConflict:
        raise
    except ThumbnailUpdateError:
        raise
    except Exception as exc:
        logger.exception("Testimony thumbnail preparation failed: id=%s", obj.pk)
        raise ThumbnailUpdateError("Could not prepare thumbnail.") from exc
    finally:
        if raw_key and raw_key != final_key:
            _delete_prepared(raw_key, protected_keys={original_key, final_key} if published else {original_key})
        if not published:
            protected = {original_key}
            for key in variant_keys:
                _delete_prepared(key, protected_keys=protected)
            if final_key:
                _delete_prepared(final_key, protected_keys=protected)
            if raw_key and raw_key == final_key:
                _delete_prepared(raw_key, protected_keys=protected)

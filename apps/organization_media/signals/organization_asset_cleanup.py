# apps/organization_media/signals/organization_asset_cleanup.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

"""Cleanup unreferenced deleted assets using the existing media cleanup helpers."""

import logging
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.content_safety.models import ContentSafetyJob
from apps.media_conversion.models import MediaConversionJob
from apps.media_conversion.services.storage_cleanup import (
    delete_job_output, delete_storage_key, delete_video_output,
)
from apps.organization_media.models import OrganizationMediaAsset

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=OrganizationMediaAsset,
          dispatch_uid="organization.media.asset.cleanup.v1")
def cleanup_organization_media_asset(sender, instance, **kwargs):
    asset_id = instance.pk
    source_name = instance.file.name if instance.file else None
    thumbnail_name = instance.thumbnail.name if instance.thumbnail else None

    def cleanup():
        ct = ContentType.objects.get_for_model(OrganizationMediaAsset)
        try:
            jobs = list(MediaConversionJob.objects.filter(content_type=ct, object_id=asset_id))
            for job in jobs:
                delete_storage_key(job.source_path, label="organization-asset.job.source")
                delete_job_output(job.kind, job.output_path,
                                  label="organization-asset.job.output")
            MediaConversionJob.objects.filter(content_type=ct, object_id=asset_id).delete()
            ContentSafetyJob.objects.filter(content_type=ct, object_id=asset_id).delete()
            if source_name:
                if source_name.lower().endswith(".m3u8"):
                    delete_video_output(source_name, label="organization-asset.file.hls")
                else:
                    delete_storage_key(source_name, label="organization-asset.file")
            if thumbnail_name:
                delete_storage_key(thumbnail_name, label="organization-asset.thumbnail")
        except Exception:
            logger.exception("organization-asset.cleanup_failed id=%s", asset_id)

    transaction.on_commit(cleanup)

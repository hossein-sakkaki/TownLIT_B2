# apps/organization_content/tasks.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

"""Durable publication intent, executed outside the iOS composer lifecycle."""

from datetime import timedelta
import logging

from celery import shared_task
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organization_content.models import OrganizationUpdate
from apps.organization_content.services.updates import publish_update

logger = logging.getLogger(__name__)

RECHECK_SECONDS = 20
MAX_WAIT = timedelta(hours=24)


@shared_task(bind=True, max_retries=4320, ignore_result=True)
def publish_organization_update(self, update_id: int):
    """Continue a committed request; retries cannot publish a discarded post."""
    should_retry = False
    with transaction.atomic():
        update = (
            OrganizationUpdate.objects.select_for_update()
            .select_related("organization", "created_by")
            .prefetch_related("media_items__asset")
            .filter(pk=update_id).first()
        )
        if update is None or not update.publish_requested_at or update.status != OrganizationUpdate.Status.DRAFT:
            return
        if timezone.now() - update.publish_requested_at > MAX_WAIT:
            update.publish_error = "Media processing did not complete. Please retry publishing."
            update.publish_requested_at = None
            update.save(update_fields=["publish_error", "publish_requested_at", "updated_at"])
            return
        assets = [usage.asset for usage in update.media_items.all()]
        if not assets:
            update.publish_error = "Add at least one photo or a video before publishing."
            update.publish_requested_at = None
            update.save(update_fields=["publish_error", "publish_requested_at", "updated_at"])
            return
        if any(asset.status in {"failed", "archived"} for asset in assets):
            update.publish_error = "Media processing failed or the asset was removed."
            update.publish_requested_at = None
            update.save(update_fields=["publish_error", "publish_requested_at", "updated_at"])
            return
        if any(not asset.is_ready_for_publication() for asset in assets):
            should_retry = True
        else:
            try:
                if update.created_by is None:
                    raise ValidationError("The publishing operator is no longer available.")
                publish_update(update=update, actor=update.created_by)
                # publish_update already holds this row lock and implements safety checks.
                update.publish_error = ""
                update.publish_requested_at = None
                update.save(update_fields=["publish_error", "publish_requested_at", "updated_at"])
            except (ValidationError, PermissionDenied) as exc:
                logger.info("organization publication stopped update=%s reason=%s", update_id, exc)
                update.publish_error = str(exc)
                update.publish_requested_at = None
                update.save(update_fields=["publish_error", "publish_requested_at", "updated_at"])
    if should_retry:
        # All retry attempts are idempotent; processing is owned by existing media jobs.
        raise self.retry(countdown=RECHECK_SECONDS)

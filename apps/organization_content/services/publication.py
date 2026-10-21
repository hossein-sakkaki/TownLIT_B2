# apps/organization_content/services/publication.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organization_content.models import OrganizationUpdate
from apps.organization_content.publishing_policy import validate_media_selection
from apps.organization_content.services.access import ensure_content_manager, ensure_update_editable
from apps.organization_content.tasks import publish_organization_update


@transaction.atomic
def request_update_publication(*, update, actor):
    update = (OrganizationUpdate.objects.select_for_update()
              .select_related("organization").get(pk=update.pk))
    ensure_content_manager(actor=actor, organization=update.organization)
    if update.status == OrganizationUpdate.Status.PUBLISHED:
        return update
    ensure_update_editable(update)
    if update.status != OrganizationUpdate.Status.DRAFT:
        raise ValidationError("Only an unpublished post can be submitted.")
    assets = [usage.asset for usage in update.media_items.select_related("asset")]
    validate_media_selection(assets, require_media=True)
    if update.publish_requested_at:
        # A retry after a broker interruption requeues the same durable intent.
        transaction.on_commit(lambda: publish_organization_update.delay(update.pk))
        return update
    update.publish_requested_at = timezone.now()
    update.publish_error = ""
    update.save(update_fields=["publish_requested_at", "publish_error", "updated_at"])
    transaction.on_commit(lambda: publish_organization_update.delay(update.pk))
    return update


@transaction.atomic
def discard_unsubmitted_update(*, update, actor):
    update = (OrganizationUpdate.objects.select_for_update()
              .select_related("organization").get(pk=update.pk))
    ensure_content_manager(actor=actor, organization=update.organization)
    if update.status != OrganizationUpdate.Status.DRAFT or update.publish_requested_at:
        raise ValidationError("Only an unsubmitted post can be discarded.")
    # Delete only assets owned exclusively by this abandoned submission.
    candidate_ids = list(update.media_items.values_list("asset_id", flat=True))
    update.delete()
    from apps.organization_media.models import OrganizationMediaAsset
    for asset in OrganizationMediaAsset.objects.select_for_update().filter(pk__in=candidate_ids):
        if (asset.created_by_id == actor.pk
                and not asset.update_usages.exists()
                and not asset.featured_intro_for_organizations.exists()):
            asset.delete()  # Existing shared media jobs are cleaned by its post_delete receiver.

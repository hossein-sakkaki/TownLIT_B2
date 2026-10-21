# apps/organization_media/services/uploads.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

import hashlib
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.content_safety.enums import SafetyContext
from apps.content_safety.services.image import enforce_image_file_safety
from apps.content_safety.services.media_jobs import schedule_configured_content_safety_jobs
from apps.content_safety.services.text import enforce_text_safety
from apps.organization_content.feature_flags import ensure_organization_content_writes_enabled
from apps.organization_content.models import OrganizationUpdate, OrganizationUpdateMedia
from apps.organization_content.publishing_policy import (
    MAX_IMAGE_BYTES, VIDEO_POLICY, validate_media_selection,
)
from apps.organization_content.services.access import ensure_content_manager, ensure_update_editable
from apps.organization_media.models import OrganizationMediaAsset
from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.mediaValidators.video_validators import validate_video_file
from validators.security_validators import validate_no_executable_file


def _enforce_image_upload_safety(*, file, actor, field_name):
    try:
        enforce_image_file_safety(
            file_obj=file, context=SafetyContext.GENERIC, actor=actor,
            field_name=field_name, mime_type=getattr(file, "content_type", None),
        )
    except (TypeError, ValueError) as exc:
        # Match the existing Moment adapter: malformed inputs are validation
        # errors. Safety block/review/unavailable exceptions must propagate.
        raise ValidationError({field_name: str(exc)}) from exc
    finally:
        file.seek(0)


def _validate_upload(*, kind, file, thumbnail, actor, alt_text, caption):
    validate_no_executable_file(file)
    if kind == OrganizationMediaAsset.Kind.IMAGE:
        validate_image_file(file)
        if file.size > MAX_IMAGE_BYTES:
            raise ValidationError({"file": f"Photos must not exceed {MAX_IMAGE_BYTES // (1024 * 1024)} MB."})
        _enforce_image_upload_safety(file=file, actor=actor, field_name="file")
    elif kind == OrganizationMediaAsset.Kind.VIDEO:
        validate_video_file(file, policy=VIDEO_POLICY)
    else:
        raise ValidationError({"kind": "Unsupported Organization media kind."})
    file.seek(0)
    if thumbnail:
        validate_no_executable_file(thumbnail)
        validate_image_file(thumbnail)
        validate_image_size(thumbnail)
        _enforce_image_upload_safety(file=thumbnail, actor=actor, field_name="thumbnail")
    for field, value in (("alt_text", alt_text), ("caption", caption)):
        if value:
            enforce_text_safety(text=value, context=SafetyContext.GENERIC, actor=actor, field_name=field)


def _file_digest(file):
    digest = hashlib.sha256()
    file.seek(0)
    for chunk in file.chunks():
        digest.update(chunk)
    file.seek(0)
    return digest.hexdigest()


def _attach_to_draft(*, asset, update):
    if update is None:
        return
    usages = list(update.media_items.select_related("asset").all())
    if any(usage.asset_id == asset.pk for usage in usages):
        return
    validate_media_selection([usage.asset for usage in usages] + [asset])
    OrganizationUpdateMedia.objects.create(
        update=update, asset=asset,
        sort_order=max((usage.sort_order for usage in usages), default=-1) + 1,
    )
    update.save(update_fields=["updated_at"])


def create_asset(*, organization, actor, kind, file, public_id=None,
                 update_public_id=None, thumbnail=None, alt_text="", caption=""):
    ensure_organization_content_writes_enabled()
    ensure_content_manager(actor=actor, organization=organization)
    public_id = public_id or uuid.uuid4()
    digest = _file_digest(file)
    # Providers and file probing run outside the row-lock transaction.
    existing = OrganizationMediaAsset.objects.filter(public_id=public_id).first()
    if existing is None:
        _validate_upload(kind=kind, file=file, thumbnail=thumbnail, actor=actor,
                         alt_text=alt_text, caption=caption)

    with transaction.atomic():
        update = None
        if update_public_id:
            update = OrganizationUpdate.objects.select_for_update().filter(
                organization=organization, public_id=update_public_id,
                status=OrganizationUpdate.Status.DRAFT,
            ).first()
            if update is None:
                raise ValidationError({"update_public_id": "An editable Organization draft was not found."})
            ensure_update_editable(update)

        # Serialize same-organization upload retries using the organization row.
        organization = organization.__class__.objects.select_for_update().get(pk=organization.pk)
        ensure_content_manager(actor=actor, organization=organization)
        existing = OrganizationMediaAsset.objects.filter(public_id=public_id).first()
        if existing is not None:
            if (existing.organization_id != organization.pk
                    or existing.created_by_id != actor.pk
                    or existing.kind != kind or existing.upload_sha256 != digest):
                raise ValidationError({"public_id": "This upload identifier is already in use."})
            _attach_to_draft(asset=existing, update=update)
            return existing

        asset = OrganizationMediaAsset(
            public_id=public_id, organization=organization, created_by=actor,
            kind=kind, file=file, thumbnail=thumbnail, alt_text=alt_text,
            caption=caption, upload_sha256=digest,
            image_safety_verified=kind == OrganizationMediaAsset.Kind.IMAGE,
            status=OrganizationMediaAsset.Status.PROCESSING,
        )
        # Reject invalid galleries before Django writes either uploaded file.
        if update is not None:
            validate_media_selection([
                usage.asset for usage in update.media_items.select_related("asset")
            ] + [asset])
        asset.full_clean()
        asset.save()
        _attach_to_draft(asset=asset, update=update)
        if kind == OrganizationMediaAsset.Kind.VIDEO:
            schedule_configured_content_safety_jobs(
                instance=asset, actor=actor, submitted_data={"file": file},
            )
        return asset

# apps/organizations/modules/church/services/teaching.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.content_safety.enums import (
    ContentSafetyJobStatus,
    SafetyDecision,
)
from apps.content_safety.models import ContentSafetyJob
from apps.content_safety.services.media_jobs import (
    schedule_configured_content_safety_jobs,
)
from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchPermissionKey,
    ChurchTeachingFormat,
    ChurchTeachingSeriesStatus,
    ChurchTeachingStatus,
)
from apps.organizations.modules.church.models import ChurchTeachingSeries
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit
from apps.posts.models.church_teaching import (
    ChurchTeachingContent,
    ChurchTeachingScriptureReference,
)
from apps.posts.services.church_teaching_content_safety import (
    enforce_church_teaching_series_text_safety,
    enforce_church_teaching_text_safety,
    enforce_church_teaching_thumbnail_safety,
)


_UNSET = object()


def _normalized_slug(value: str) -> str:
    normalized = slugify(value or "")[:180]
    return normalized or "teaching-series"


def _unique_series_slug(*, workspace, name: str) -> str:
    base = _normalized_slug(name)
    candidate = base
    index = 1

    while ChurchTeachingSeries.objects.filter(
        workspace=workspace,
        slug=candidate,
    ).exists():
        suffix = f"-{index}"
        candidate = f"{base[:180 - len(suffix)]}{suffix}"
        index += 1

    return candidate


def _speaker_snapshot(*, speaker_membership, external_speaker_name: str) -> str:
    if speaker_membership is not None:
        member = speaker_membership.member
        user = member.user
        display = " ".join(
            value
            for value in (
                str(getattr(user, "name", "") or "").strip(),
                str(getattr(user, "family", "") or "").strip(),
            )
            if value
        ).strip()

        return display or str(getattr(user, "username", "") or "").strip()

    return " ".join(str(external_speaker_name or "").split())


def _validate_active_speaker_membership(*, workspace, speaker_membership) -> None:
    if speaker_membership is None:
        return

    organization_id = workspace.activation.organization_id

    authoritative = (
        speaker_membership.__class__.objects
        .filter(
            pk=speaker_membership.pk,
            organization_id=organization_id,
            status=OrganizationMembershipStatus.ACTIVE,
        )
        .exists()
    )

    if not authoritative:
        raise ValidationError({
            "speaker_membership": (
                "Organization speaker must have an active official membership "
                "in the same organization."
            ),
        })


def _replace_scripture_references(*, content, references) -> None:
    ChurchTeachingScriptureReference.objects.filter(content=content).delete()

    rows = []
    for index, raw in enumerate(references or []):
        if isinstance(raw, str):
            reference_text = raw
            normalized = {}
        elif isinstance(raw, dict):
            reference_text = raw.get("reference_text") or raw.get("reference") or ""
            normalized = raw.get("normalized") or {}
        else:
            raise ValidationError({
                "scripture_references": "Scripture references must be strings or objects.",
            })

        reference_text = " ".join(str(reference_text or "").split())
        if not reference_text:
            continue

        row = ChurchTeachingScriptureReference(
            content=content,
            reference_text=reference_text,
            sort_order=index,
            normalized=normalized if isinstance(normalized, dict) else {},
        )
        row.full_clean()
        rows.append(row)

    if rows:
        ChurchTeachingScriptureReference.objects.bulk_create(rows)


def create_church_teaching_series(
    *,
    workspace,
    actor,
    name: str,
    description: str = "",
    campus=None,
    ministry=None,
    sort_order: int = 0,
    metadata=None,
) -> ChurchTeachingSeries:
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_TEACHING,
    )

    enforce_church_teaching_series_text_safety(
        name=name,
        description=description,
        actor=actor,
    )

    with transaction.atomic():
        locked_workspace = (
            workspace.__class__.objects
            .select_for_update()
            .get(pk=workspace.pk)
        )

        series = ChurchTeachingSeries(
            workspace=locked_workspace,
            campus=campus,
            ministry=ministry,
            name=name,
            slug=_unique_series_slug(
                workspace=locked_workspace,
                name=name,
            ),
            description=description or "",
            status=ChurchTeachingSeriesStatus.ACTIVE,
            sort_order=max(0, int(sort_order or 0)),
            metadata=metadata or {},
        )
        series.full_clean()
        series.save()

        record_church_audit(
            workspace=locked_workspace,
            event=ChurchAuditEvent.TEACHING_SERIES_CREATED,
            actor=actor,
            entity=series,
            metadata={
                "campus_id": series.campus_id,
                "ministry_id": series.ministry_id,
            },
        )

    return series


def update_church_teaching_series(
    *,
    series,
    actor,
    name=None,
    description=None,
    campus=_UNSET,
    ministry=_UNSET,
    sort_order=None,
    metadata=None,
) -> ChurchTeachingSeries:
    current = (
        ChurchTeachingSeries.objects
        .select_related(
            "workspace__activation__organization",
            "campus",
            "ministry",
        )
        .get(pk=series.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=current.workspace,
        permission_key=ChurchPermissionKey.MANAGE_TEACHING,
    )

    if current.status == ChurchTeachingSeriesStatus.ARCHIVED:
        raise ValidationError(
            "Archived teaching series cannot be edited."
        )

    enforce_church_teaching_series_text_safety(
        name=name,
        description=description,
        actor=actor,
    )

    with transaction.atomic():
        locked = (
            ChurchTeachingSeries.objects
            .select_for_update()
            .select_related(
                "workspace__activation__organization",
                "campus",
                "ministry",
            )
            .get(pk=series.pk)
        )

        if locked.status == ChurchTeachingSeriesStatus.ARCHIVED:
            raise ValidationError(
                "Archived teaching series cannot be edited."
            )

        if name is not None:
            locked.name = name
        if description is not None:
            locked.description = description
        if campus is not _UNSET:
            locked.campus = campus
        if ministry is not _UNSET:
            locked.ministry = ministry
        if sort_order is not None:
            locked.sort_order = max(0, int(sort_order))
        if metadata is not None:
            locked.metadata = metadata

        locked.full_clean()
        locked.save()

        record_church_audit(
            workspace=locked.workspace,
            event=ChurchAuditEvent.TEACHING_SERIES_UPDATED,
            actor=actor,
            entity=locked,
            metadata={
                "campus_id": locked.campus_id,
                "ministry_id": locked.ministry_id,
            },
        )

    return locked


@transaction.atomic
def archive_church_teaching_series(*, series, actor) -> ChurchTeachingSeries:
    locked = ChurchTeachingSeries.objects.select_for_update().select_related(
        "workspace__activation__organization",
    ).get(pk=series.pk)

    ensure_church_permission(
        actor=actor,
        workspace=locked.workspace,
        permission_key=ChurchPermissionKey.PUBLISH_TEACHING,
    )

    if locked.status == ChurchTeachingSeriesStatus.ARCHIVED:
        return locked

    locked.status = ChurchTeachingSeriesStatus.ARCHIVED
    locked.full_clean()
    locked.save(update_fields=["status", "updated_at"])

    record_church_audit(
        workspace=locked.workspace,
        event=ChurchAuditEvent.TEACHING_SERIES_ARCHIVED,
        actor=actor,
        entity=locked,
    )

    return locked


def create_church_teaching_content(
    *,
    workspace,
    actor,
    teaching_type,
    content_format,
    title: str,
    audience,
    speaker_membership=None,
    external_speaker_name: str = "",
    excerpt: str = "",
    body: str = "",
    video=None,
    thumbnail=None,
    series=None,
    campus=None,
    ministry=None,
    occurrence=None,
    service_plan_item=None,
    scripture_references=None,
    metadata=None,
) -> ChurchTeachingContent:
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_TEACHING,
    )

    _validate_active_speaker_membership(
        workspace=workspace,
        speaker_membership=speaker_membership,
    )

    speaker_name = _speaker_snapshot(
        speaker_membership=speaker_membership,
        external_speaker_name=external_speaker_name,
    )

    if not speaker_name:
        raise ValidationError({
            "speaker": "An organization member speaker or external speaker name is required.",
        })

    enforce_church_teaching_text_safety(
        title=title,
        excerpt=excerpt,
        body=body,
        speaker_name=(
            external_speaker_name
            if speaker_membership is None
            else None
        ),
        actor=actor,
    )
    enforce_church_teaching_thumbnail_safety(
        thumbnail=thumbnail,
        actor=actor,
    )

    if service_plan_item is not None and occurrence is None:
        occurrence = service_plan_item.service_plan.occurrence

    with transaction.atomic():
        content = ChurchTeachingContent(
            workspace=workspace,
            series=series,
            campus=campus,
            ministry=ministry,
            occurrence=occurrence,
            service_plan_item=service_plan_item,
            teaching_type=teaching_type,
            content_format=content_format,
            status=ChurchTeachingStatus.DRAFT,
            audience=audience,
            title=title,
            excerpt=excerpt or "",
            body=body or "",
            speaker_membership=speaker_membership,
            speaker_name_snapshot=speaker_name,
            video=video,
            thumbnail=thumbnail,
            created_by=actor,
            updated_by=actor,
            metadata=metadata or {},
        )
        content.full_clean()
        content.save()

        _replace_scripture_references(
            content=content,
            references=scripture_references,
        )

        if content_format == ChurchTeachingFormat.VIDEO and video:
            schedule_configured_content_safety_jobs(
                instance=content,
                actor=actor,
                submitted_data={"video": video},
            )

        record_church_audit(
            workspace=workspace,
            event=ChurchAuditEvent.TEACHING_CONTENT_CREATED,
            actor=actor,
            entity=content,
            metadata={
                "teaching_type": content.teaching_type,
                "content_format": content.content_format,
                "audience": content.audience,
                "series_id": content.series_id,
                "occurrence_id": content.occurrence_id,
            },
        )

    return content


def update_church_teaching_content(
    *,
    content,
    actor,
    title=None,
    excerpt=None,
    body=None,
    audience=None,
    speaker_membership=_UNSET,
    external_speaker_name=_UNSET,
    series=_UNSET,
    campus=_UNSET,
    ministry=_UNSET,
    occurrence=_UNSET,
    service_plan_item=_UNSET,
    scripture_references=None,
    metadata=None,
) -> ChurchTeachingContent:
    current = ChurchTeachingContent.objects.select_related(
        "workspace__activation__organization",
        "speaker_membership__member__user",
    ).get(pk=content.pk)

    if current.status != ChurchTeachingStatus.DRAFT:
        raise ValidationError("Published or archived teaching content is immutable.")

    ensure_church_permission(
        actor=actor,
        workspace=current.workspace,
        permission_key=ChurchPermissionKey.MANAGE_TEACHING,
    )

    effective_title = current.title if title is None else title
    effective_excerpt = current.excerpt if excerpt is None else excerpt
    effective_body = current.body if body is None else body

    enforce_church_teaching_text_safety(
        title=effective_title if title is not None else None,
        excerpt=effective_excerpt if excerpt is not None else None,
        body=effective_body if body is not None else None,
        speaker_name=(
            external_speaker_name
            if external_speaker_name is not _UNSET
            else None
        ),
        actor=actor,
    )

    with transaction.atomic():
        locked = ChurchTeachingContent.objects.select_for_update().select_related(
            "workspace__activation__organization",
            "speaker_membership__member__user",
        ).get(pk=content.pk)

        if locked.status != ChurchTeachingStatus.DRAFT:
            raise ValidationError("Published or archived teaching content is immutable.")

        if title is not None:
            locked.title = title
        if excerpt is not None:
            locked.excerpt = excerpt
        if body is not None:
            locked.body = body
        if audience is not None:
            locked.audience = audience
        if series is not _UNSET:
            locked.series = series
        if campus is not _UNSET:
            locked.campus = campus
        if ministry is not _UNSET:
            locked.ministry = ministry
        if occurrence is not _UNSET:
            locked.occurrence = occurrence
        if service_plan_item is not _UNSET:
            locked.service_plan_item = service_plan_item
            if service_plan_item is not None and occurrence is _UNSET:
                locked.occurrence = service_plan_item.service_plan.occurrence
        if metadata is not None:
            locked.metadata = metadata

        if speaker_membership is not _UNSET:
            if speaker_membership is None:
                if external_speaker_name is _UNSET:
                    raise ValidationError({
                        "speaker": (
                            "Clearing an organization speaker requires an external speaker name."
                        ),
                    })
            else:
                _validate_active_speaker_membership(
                    workspace=locked.workspace,
                    speaker_membership=speaker_membership,
                )
                locked.speaker_membership = speaker_membership
                locked.speaker_name_snapshot = _speaker_snapshot(
                    speaker_membership=speaker_membership,
                    external_speaker_name="",
                )

        if external_speaker_name is not _UNSET:
            locked.speaker_membership = None
            locked.speaker_name_snapshot = _speaker_snapshot(
                speaker_membership=None,
                external_speaker_name=external_speaker_name,
            )

        locked.updated_by = actor
        locked.full_clean()
        locked.save()

        if scripture_references is not None:
            _replace_scripture_references(
                content=locked,
                references=scripture_references,
            )

        record_church_audit(
            workspace=locked.workspace,
            event=ChurchAuditEvent.TEACHING_CONTENT_UPDATED,
            actor=actor,
            entity=locked,
            metadata={
                "teaching_type": locked.teaching_type,
                "content_format": locked.content_format,
                "audience": locked.audience,
            },
        )

    return locked


def _video_safety_is_approved(content: ChurchTeachingContent) -> bool:
    content_type = ContentType.objects.get_for_model(
        content,
        for_concrete_model=False,
    )

    job = ContentSafetyJob.objects.filter(
        content_type=content_type,
        object_id=content.pk,
        field_name="video",
    ).order_by("-updated_at", "-id").first()

    return bool(
        job
        and job.status == ContentSafetyJobStatus.DONE
        and job.decision == SafetyDecision.ALLOW
    )


@transaction.atomic
def publish_church_teaching_content(*, content, actor) -> ChurchTeachingContent:
    locked = ChurchTeachingContent.objects.select_for_update().select_related(
        "workspace__activation__organization",
    ).get(pk=content.pk)

    ensure_church_permission(
        actor=actor,
        workspace=locked.workspace,
        permission_key=ChurchPermissionKey.PUBLISH_TEACHING,
    )

    if locked.status == ChurchTeachingStatus.PUBLISHED:
        return locked

    if locked.status != ChurchTeachingStatus.DRAFT:
        raise ValidationError("Only draft teaching content can be published.")

    if locked.content_format == ChurchTeachingFormat.VIDEO:
        if not locked.video or not locked.is_converted:
            raise ValidationError(
                "Video teaching cannot be published until Media Conversion is complete."
            )

        if not _video_safety_is_approved(locked):
            raise ValidationError(
                "Video teaching cannot be published until Content Safety allows the source."
            )

    locked.status = ChurchTeachingStatus.PUBLISHED
    locked.published_at = timezone.now()
    locked.published_by = actor
    locked.updated_by = actor
    locked.full_clean()
    locked.save(
        update_fields=[
            "status",
            "published_at",
            "published_by",
            "updated_by",
            "updated_at",
        ]
    )

    record_church_audit(
        workspace=locked.workspace,
        event=ChurchAuditEvent.TEACHING_CONTENT_PUBLISHED,
        actor=actor,
        entity=locked,
        metadata={
            "teaching_type": locked.teaching_type,
            "content_format": locked.content_format,
            "audience": locked.audience,
        },
    )

    if locked.content_format == ChurchTeachingFormat.VIDEO:
        content_id = locked.pk

        def _ensure_published_subtitles():
            from apps.posts.models.church_teaching import ChurchTeachingContent
            from apps.subtitles.services.organization_orchestrator import (
                enqueue_organization_subtitles_for_target,
            )

            published = ChurchTeachingContent.objects.filter(
                pk=content_id,
                status=ChurchTeachingStatus.PUBLISHED,
            ).first()

            if published is not None:
                enqueue_organization_subtitles_for_target(published)

        transaction.on_commit(_ensure_published_subtitles)

    return locked


@transaction.atomic
def archive_church_teaching_content(*, content, actor) -> ChurchTeachingContent:
    locked = ChurchTeachingContent.objects.select_for_update().select_related(
        "workspace__activation__organization",
    ).get(pk=content.pk)

    ensure_church_permission(
        actor=actor,
        workspace=locked.workspace,
        permission_key=ChurchPermissionKey.PUBLISH_TEACHING,
    )

    if locked.status == ChurchTeachingStatus.ARCHIVED:
        return locked

    locked.status = ChurchTeachingStatus.ARCHIVED
    locked.archived_at = timezone.now()
    locked.archived_by = actor
    locked.updated_by = actor
    locked.full_clean()
    locked.save(
        update_fields=[
            "status",
            "archived_at",
            "archived_by",
            "updated_by",
            "updated_at",
        ]
    )

    record_church_audit(
        workspace=locked.workspace,
        event=ChurchAuditEvent.TEACHING_CONTENT_ARCHIVED,
        actor=actor,
        entity=locked,
        metadata={
            "previously_published": bool(locked.published_at),
        },
    )

    return locked


@transaction.atomic
def delete_draft_church_teaching_content(*, content, actor) -> None:
    locked = ChurchTeachingContent.objects.select_for_update().select_related(
        "workspace__activation__organization",
    ).get(pk=content.pk)

    ensure_church_permission(
        actor=actor,
        workspace=locked.workspace,
        permission_key=ChurchPermissionKey.MANAGE_TEACHING,
    )

    if locked.status != ChurchTeachingStatus.DRAFT:
        raise ValidationError("Published teaching must be archived, not deleted.")

    public_id = locked.public_id
    workspace = locked.workspace

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.TEACHING_CONTENT_DELETED,
        actor=actor,
        entity_type="ChurchTeachingContent",
        entity_public_id=public_id,
        metadata={
            "teaching_type": locked.teaching_type,
            "content_format": locked.content_format,
        },
    )

    locked.delete()

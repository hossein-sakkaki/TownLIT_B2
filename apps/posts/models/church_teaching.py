# apps/posts/models/church_teaching.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.content_safety.enums import SafetyContext, SafetyInputType
from apps.content_safety.mixins import ContentSafetyMediaTargetMixin
from apps.core.availability.interfaces import AvailabilityAware
from apps.core.interactions.mixins import InteractionCounterMixin
from apps.core.interactions.models import ReactionBreakdownMixin
from apps.core.moderation.mixins import ModerationTargetMixin
from apps.organizations.modules.church.constants import (
    ChurchServicePlanItemType,
    ChurchTeachingAudience,
    ChurchTeachingContentType,
    ChurchTeachingFormat,
    ChurchTeachingStatus,
)
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


class ChurchTeachingContent(
    ModerationTargetMixin,
    InteractionCounterMixin,
    ReactionBreakdownMixin,
    MediaAssetsMixin,
    ContentSafetyMediaTargetMixin,
    MediaAutoConvertMixin,
    MediaConversionMixin,
    SlugMixin,
    AvailabilityAware,
    models.Model,
):
    """Organization-owned Church sermon or teaching content."""

    AUTO_THUMBNAIL_FROM_VIDEO = True
    SLUG_ALLOW_UNICODE = True

    VIDEO = FileUpload(
        "posts",
        "videos",
        "church_teaching",
    )
    THUMBNAIL = FileUpload(
        "posts",
        "photos",
        "church_teaching",
    )

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    workspace = models.ForeignKey(
        "organizations.ChurchWorkspace",
        on_delete=models.CASCADE,
        related_name="teaching_contents",
    )
    series = models.ForeignKey(
        "organizations.ChurchTeachingSeries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contents",
    )
    campus = models.ForeignKey(
        "organizations.ChurchCampus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_contents",
    )
    ministry = models.ForeignKey(
        "organizations.ChurchMinistry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_contents",
    )
    occurrence = models.ForeignKey(
        "organizations.ChurchGatheringOccurrence",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_contents",
    )
    service_plan_item = models.ForeignKey(
        "organizations.ChurchServicePlanItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_contents",
    )

    teaching_type = models.CharField(
        max_length=30,
        choices=ChurchTeachingContentType.choices,
        default=ChurchTeachingContentType.SERMON,
        db_index=True,
    )
    content_format = models.CharField(
        max_length=16,
        choices=ChurchTeachingFormat.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=16,
        choices=ChurchTeachingStatus.choices,
        default=ChurchTeachingStatus.DRAFT,
        db_index=True,
    )
    audience = models.CharField(
        max_length=30,
        choices=ChurchTeachingAudience.choices,
        default=ChurchTeachingAudience.PUBLIC,
        db_index=True,
    )

    title = models.CharField(max_length=220)
    excerpt = models.CharField(max_length=1000, blank=True, default="")
    body = models.TextField(blank=True, default="")

    speaker_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_teaching_contents_spoken",
    )
    speaker_name_snapshot = models.CharField(max_length=180)

    video = models.FileField(
        upload_to=VIDEO,
        max_length=700,
        null=True,
        blank=True,
        validators=[validate_no_executable_file],
    )
    thumbnail = models.ImageField(
        upload_to=THUMBNAIL,
        max_length=700,
        null=True,
        blank=True,
        validators=[
            validate_image_file,
            validate_image_size,
            validate_no_executable_file,
        ],
    )

    is_converted = models.BooleanField(default=True, db_index=True)

    reactions = GenericRelation(
        "posts.Reaction",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="church_teaching_targets",
    )
    comments = GenericRelation(
        "posts.Comment",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="church_teaching_targets",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_teaching_contents_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_teaching_contents_updated",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_teaching_contents_published",
    )
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_teaching_contents_archived",
    )

    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    media_conversion_config = {
        "video": {
            "upload": VIDEO,
            "kind": "video",
            "required_for_availability": True,
        },
        "thumbnail": {
            "upload": THUMBNAIL,
            "kind": "image",
            "required_for_availability": False,
        },
    }

    content_safety_media_config = {
        "video": {
            "input_type": SafetyInputType.VIDEO,
            "context": SafetyContext.GENERIC,
            "conversion_kind": "video",
        },
    }

    class Meta:
        verbose_name = "Church Teaching Content"
        verbose_name_plural = "Church Teaching Content"
        ordering = ("-published_at", "-created_at", "-id")
        indexes = [
            models.Index(fields=["workspace", "status", "created_at"]),
            models.Index(fields=["workspace", "audience", "status"]),
            models.Index(fields=["series", "status", "published_at"]),
            models.Index(fields=["occurrence", "status"]),
            models.Index(fields=["teaching_type", "content_format", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(
                        status=ChurchTeachingStatus.DRAFT,
                        published_at__isnull=True,
                        archived_at__isnull=True,
                    )
                    | Q(
                        status=ChurchTeachingStatus.PUBLISHED,
                        published_at__isnull=False,
                        archived_at__isnull=True,
                    )
                    | Q(
                        status=ChurchTeachingStatus.ARCHIVED,
                        archived_at__isnull=False,
                    )
                ),
                name="posts_church_teaching_status_consistent",
            ),
        ]

    def get_slug_source(self) -> str:
        organization = self.workspace.activation.organization
        return f"{organization.name} {self.title}"

    def clean(self):
        super().clean()

        self._validate_church_scope()
        self._validate_format_payload()
        self._validate_speaker()
        self._validate_lifecycle()

    def _validate_church_scope(self):
        workspace_id = self.workspace_id

        for field_name in ("series", "campus", "ministry", "occurrence"):
            value = getattr(self, field_name, None)
            if value is not None and value.workspace_id != workspace_id:
                raise ValidationError({
                    field_name: "Teaching context must belong to the same Church workspace.",
                })

        if self.service_plan_item_id:
            plan = self.service_plan_item.service_plan

            if self.service_plan_item.item_type != ChurchServicePlanItemType.SERMON:
                raise ValidationError({
                    "service_plan_item": (
                        "Church teaching can link only to a Sermon service plan item in V1."
                    ),
                })

            if plan.workspace_id != workspace_id:
                raise ValidationError({
                    "service_plan_item": "Service plan item must belong to the same Church workspace.",
                })

            if self.occurrence_id and plan.occurrence_id != self.occurrence_id:
                raise ValidationError({
                    "service_plan_item": "Service plan item belongs to a different gathering occurrence.",
                })

        if (
            self.campus_id
            and self.ministry_id
            and self.ministry.campus_id
            and self.ministry.campus_id != self.campus_id
        ):
            raise ValidationError({
                "ministry": "Teaching ministry belongs to a different campus.",
            })

    def _validate_format_payload(self):
        if self.content_format == ChurchTeachingFormat.WRITTEN:
            if not str(self.body or "").strip():
                raise ValidationError({
                    "body": "Written Church teaching requires body content.",
                })
            if self.video:
                raise ValidationError({
                    "video": "Written Church teaching cannot contain a video source.",
                })

        if self.content_format == ChurchTeachingFormat.VIDEO and not self.video:
            raise ValidationError({
                "video": "Video Church teaching requires a video source.",
            })

    def _validate_speaker(self):
        if not str(self.speaker_name_snapshot or "").strip():
            raise ValidationError({
                "speaker_name_snapshot": "A public speaker name is required.",
            })

        if self.speaker_membership_id:
            organization_id = self.workspace.activation.organization_id
            if self.speaker_membership.organization_id != organization_id:
                raise ValidationError({
                    "speaker_membership": "Speaker membership belongs to a different organization.",
                })

    def _validate_lifecycle(self):
        if self.status == ChurchTeachingStatus.DRAFT:
            if self.published_at or self.archived_at:
                raise ValidationError("Draft teaching cannot have publish/archive timestamps.")

        if self.status == ChurchTeachingStatus.PUBLISHED:
            if not self.published_at or self.archived_at:
                raise ValidationError("Published teaching requires a publish timestamp only.")

        if self.status == ChurchTeachingStatus.ARCHIVED and not self.archived_at:
            raise ValidationError("Archived teaching requires archived_at.")

    def media_autoconvert_enabled(self) -> bool:
        return self.content_format == ChurchTeachingFormat.VIDEO

    def is_available(self) -> bool:
        if self.content_format == ChurchTeachingFormat.WRITTEN:
            return True

        return bool(self.video and self.is_converted)

    def on_available(self):
        if self.content_format != ChurchTeachingFormat.VIDEO:
            return

        from apps.subtitles.services.organization_orchestrator import (
            enqueue_organization_subtitles_for_target,
        )

        enqueue_organization_subtitles_for_target(self)

    def can_deliver_asset(
        self,
        *,
        viewer,
        field_name: str,
        intent: str,
    ) -> bool:
        if field_name not in {"video", "thumbnail"}:
            return False

        if intent == "download":
            return False

        if field_name == "video" and not self.is_available():
            return False

        if field_name == "thumbnail" and not self.thumbnail:
            return False

        from apps.posts.services.church_teaching_access import (
            can_view_church_teaching_content,
        )

        return can_view_church_teaching_content(
            content=self,
            viewer=viewer,
            include_manager_preview=True,
        )

    def save(self, *args, **kwargs):
        self.title = " ".join(str(self.title or "").split())
        self.excerpt = str(self.excerpt or "").strip()
        self.body = str(self.body or "").strip()
        self.speaker_name_snapshot = " ".join(
            str(self.speaker_name_snapshot or "").split()
        )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} · {self.get_teaching_type_display()}"


class ChurchTeachingScriptureReference(models.Model):
    """Ordered scripture reference attached to Church teaching content."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    content = models.ForeignKey(
        ChurchTeachingContent,
        on_delete=models.CASCADE,
        related_name="scripture_references",
    )
    reference_text = models.CharField(max_length=180)
    sort_order = models.PositiveIntegerField(default=0)
    normalized = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Church Teaching Scripture Reference"
        verbose_name_plural = "Church Teaching Scripture References"
        ordering = ("sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["content", "sort_order"],
                name="posts_church_teaching_unique_scripture_order",
            ),
        ]
        indexes = [
            models.Index(fields=["content", "sort_order"]),
        ]

    def save(self, *args, **kwargs):
        self.reference_text = " ".join(str(self.reference_text or "").split())
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.reference_text

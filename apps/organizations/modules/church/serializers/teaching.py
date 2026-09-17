# apps/organizations/modules/church/serializers/teaching.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

import json

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.media_conversion.services.serializer_gate import gate_media_payload
from apps.organizations.modules.church.constants import (
    ChurchTeachingAudience,
    ChurchTeachingContentType,
    ChurchTeachingFormat,
    ChurchTeachingSeriesStatus,
    ChurchTeachingStatus,
)
from apps.organizations.modules.church.models import ChurchTeachingSeries
from apps.posts.models.church_teaching import (
    ChurchTeachingContent,
    ChurchTeachingScriptureReference,
)


class FlexibleJSONField(serializers.JSONField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError("Invalid JSON value.") from exc
        return super().to_internal_value(data)


class ChurchTeachingScriptureReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChurchTeachingScriptureReference
        fields = [
            "public_id",
            "reference_text",
            "sort_order",
            "normalized",
        ]
        read_only_fields = fields


class ChurchTeachingSeriesSerializer(serializers.ModelSerializer):
    campus_public_id = serializers.UUIDField(
        source="campus.public_id",
        read_only=True,
        allow_null=True,
    )
    ministry_public_id = serializers.UUIDField(
        source="ministry.public_id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ChurchTeachingSeries
        fields = [
            "public_id",
            "campus_public_id",
            "ministry_public_id",
            "name",
            "slug",
            "description",
            "status",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchTeachingSeriesCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )
    campus_public_id = serializers.UUIDField(required=False, allow_null=True)
    ministry_public_id = serializers.UUIDField(required=False, allow_null=True)
    sort_order = serializers.IntegerField(required=False, default=0, min_value=0)
    metadata = FlexibleJSONField(required=False, default=dict)


class ChurchTeachingSeriesUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=180)
    description = serializers.CharField(required=False, allow_blank=True)
    campus_public_id = serializers.UUIDField(required=False, allow_null=True)
    ministry_public_id = serializers.UUIDField(required=False, allow_null=True)
    sort_order = serializers.IntegerField(required=False, min_value=0)
    metadata = FlexibleJSONField(required=False)


class ChurchTeachingContentSerializer(serializers.ModelSerializer):
    series_public_id = serializers.UUIDField(
        source="series.public_id",
        read_only=True,
        allow_null=True,
    )
    campus_public_id = serializers.UUIDField(
        source="campus.public_id",
        read_only=True,
        allow_null=True,
    )
    ministry_public_id = serializers.UUIDField(
        source="ministry.public_id",
        read_only=True,
        allow_null=True,
    )
    occurrence_public_id = serializers.UUIDField(
        source="occurrence.public_id",
        read_only=True,
        allow_null=True,
    )
    service_plan_item_public_id = serializers.UUIDField(
        source="service_plan_item.public_id",
        read_only=True,
        allow_null=True,
    )
    speaker_membership_public_id = serializers.UUIDField(
        source="speaker_membership.public_id",
        read_only=True,
        allow_null=True,
    )
    speaker_user = serializers.SerializerMethodField()
    scripture_references = ChurchTeachingScriptureReferenceSerializer(
        many=True,
        read_only=True,
    )
    has_video = serializers.SerializerMethodField()
    has_thumbnail = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    media_pipeline = serializers.SerializerMethodField()
    asset_target = serializers.SerializerMethodField()

    class Meta:
        model = ChurchTeachingContent
        fields = [
            "public_id",
            "series_public_id",
            "campus_public_id",
            "ministry_public_id",
            "occurrence_public_id",
            "service_plan_item_public_id",
            "teaching_type",
            "content_format",
            "status",
            "audience",
            "title",
            "excerpt",
            "body",
            "speaker_membership_public_id",
            "speaker_user",
            "speaker_name_snapshot",
            "scripture_references",
            "has_video",
            "has_thumbnail",
            "is_converted",
            "is_available",
            "media_pipeline",
            "asset_target",
            "published_at",
            "archived_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_speaker_user(self, obj):
        if not obj.speaker_membership_id:
            return None
        return UserMiniSerializer(
            obj.speaker_membership.member.user,
            context=self.context,
        ).data

    def get_has_video(self, obj):
        return bool(obj.video)

    def get_has_thumbnail(self, obj):
        return bool(obj.thumbnail)

    def get_is_available(self, obj):
        return bool(obj.is_available())

    def get_media_pipeline(self, obj):
        if not obj.video:
            return None

        request = self.context.get("request")
        payload = gate_media_payload(
            obj=obj,
            data={},
            viewer=getattr(request, "user", None),
            field_name="video",
            require_job=False,
            include_job_target=False,
        )
        return payload.get("media_pipeline")

    def get_asset_target(self, obj):
        return {
            "app_label": obj._meta.app_label,
            "model": obj._meta.model_name,
            "object_id": obj.pk,
        }


class _SpeakerValidationMixin:
    def _validate_speaker_choice(self, attrs, *, require_choice):
        membership_present = "speaker_membership_public_id" in attrs
        external_present = "external_speaker_name" in attrs

        membership = attrs.get("speaker_membership_public_id")
        external = " ".join(
            str(attrs.get("external_speaker_name") or "").split()
        )

        if membership and external:
            raise serializers.ValidationError({
                "speaker": "Choose either an organization speaker or an external speaker, not both.",
            })

        if require_choice and not membership and not external:
            raise serializers.ValidationError({
                "speaker": "An organization speaker or external speaker name is required.",
            })

        if membership_present and membership is None and not external:
            raise serializers.ValidationError({
                "speaker": "Clearing an organization speaker requires an external speaker name.",
            })

        if external_present and not external and not membership:
            raise serializers.ValidationError({
                "external_speaker_name": "External speaker name cannot be blank when changing the speaker.",
            })

        if external_present:
            attrs["external_speaker_name"] = external

        return attrs


class ChurchTeachingContentCreateSerializer(
    _SpeakerValidationMixin,
    serializers.Serializer,
):
    teaching_type = serializers.ChoiceField(
        choices=ChurchTeachingContentType.choices,
    )
    content_format = serializers.ChoiceField(
        choices=ChurchTeachingFormat.choices,
    )
    title = serializers.CharField(max_length=220)
    audience = serializers.ChoiceField(
        choices=ChurchTeachingAudience.choices,
    )
    speaker_membership_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    external_speaker_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=180,
    )
    excerpt = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=1000,
    )
    body = serializers.CharField(required=False, allow_blank=True, default="")
    video = serializers.FileField(required=False, allow_null=True)
    thumbnail = serializers.ImageField(required=False, allow_null=True)
    series_public_id = serializers.UUIDField(required=False, allow_null=True)
    campus_public_id = serializers.UUIDField(required=False, allow_null=True)
    ministry_public_id = serializers.UUIDField(required=False, allow_null=True)
    occurrence_public_id = serializers.UUIDField(required=False, allow_null=True)
    service_plan_item_public_id = serializers.UUIDField(required=False, allow_null=True)
    scripture_references = FlexibleJSONField(required=False, default=list)
    metadata = FlexibleJSONField(required=False, default=dict)

    def validate(self, attrs):
        attrs = self._validate_speaker_choice(attrs, require_choice=True)

        content_format = attrs.get("content_format")
        body = str(attrs.get("body") or "").strip()
        video = attrs.get("video")

        if content_format == ChurchTeachingFormat.WRITTEN:
            if not body:
                raise serializers.ValidationError({
                    "body": "Written Church teaching requires body content.",
                })
            if video:
                raise serializers.ValidationError({
                    "video": "Written Church teaching cannot contain a video source.",
                })

        if content_format == ChurchTeachingFormat.VIDEO and not video:
            raise serializers.ValidationError({
                "video": "Video Church teaching requires a video source.",
            })

        references = attrs.get("scripture_references") or []
        if not isinstance(references, list):
            raise serializers.ValidationError({
                "scripture_references": "Scripture references must be a JSON list.",
            })

        metadata = attrs.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise serializers.ValidationError({
                "metadata": "Metadata must be a JSON object.",
            })

        return attrs


class ChurchTeachingContentUpdateSerializer(
    _SpeakerValidationMixin,
    serializers.Serializer,
):
    title = serializers.CharField(required=False, max_length=220)
    excerpt = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    body = serializers.CharField(required=False, allow_blank=True)
    audience = serializers.ChoiceField(
        choices=ChurchTeachingAudience.choices,
        required=False,
    )
    speaker_membership_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    external_speaker_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=180,
    )
    series_public_id = serializers.UUIDField(required=False, allow_null=True)
    campus_public_id = serializers.UUIDField(required=False, allow_null=True)
    ministry_public_id = serializers.UUIDField(required=False, allow_null=True)
    occurrence_public_id = serializers.UUIDField(required=False, allow_null=True)
    service_plan_item_public_id = serializers.UUIDField(required=False, allow_null=True)
    scripture_references = FlexibleJSONField(required=False)
    metadata = FlexibleJSONField(required=False)

    def validate(self, attrs):
        attrs = self._validate_speaker_choice(attrs, require_choice=False)

        if "scripture_references" in attrs:
            references = attrs.get("scripture_references")
            if references is None:
                references = []
                attrs["scripture_references"] = references
            if not isinstance(references, list):
                raise serializers.ValidationError({
                    "scripture_references": "Scripture references must be a JSON list.",
                })

        if "metadata" in attrs and not isinstance(attrs.get("metadata"), dict):
            raise serializers.ValidationError({
                "metadata": "Metadata must be a JSON object.",
            })

        return attrs


class ChurchTeachingSpeakerReferenceSerializer(serializers.Serializer):
    membership_public_id = serializers.UUIDField()
    user = serializers.DictField()


class ChurchTeachingServicePlanItemReferenceSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    title = serializers.CharField()
    service_plan_public_id = serializers.UUIDField()
    occurrence_public_id = serializers.UUIDField()
    occurrence_title = serializers.CharField()
    starts_at = serializers.DateTimeField()

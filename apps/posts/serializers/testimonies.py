# apps/posts/serializers/testimonies.py
from rest_framework import serializers
import logging
import traceback
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

from apps.posts.models.testimony import Testimony
from common.file_handlers.media_mixins import (
    AudioFileMixin, VideoFileMixin, ThumbnailFileMixin
)
from .serializers_owner_min import build_owner_union_from_content_object
from common.serializers.targets import InstanceTargetMixin

logger = logging.getLogger(__name__)
CustomUser = get_user_model()


class TestimonySerializer(
    InstanceTargetMixin,
    AudioFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
    serializers.ModelSerializer
):
    """
    Unified serializer for written/audio/video testimonies.
    - GFK content_object determines the OWNER.
    - InstanceTargetMixin determines comment/reaction targets ONLY.
    """

    owner = serializers.SerializerMethodField(read_only=True)

    # Real GFK fields (read-only)
    content_type = serializers.PrimaryKeyRelatedField(read_only=True)
    object_id = serializers.IntegerField(read_only=True)

    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Testimony
        fields = [
            'id', 'slug',
            'type', 'title',
            'content', 'audio', 'video',
            'thumbnail',
            'published_at', 'updated_at',
            'is_active',
            'content_type', 'object_id',
            'comment_target', 'reaction_target',
            'is_converted',
            'owner',
        ]
        read_only_fields = [
            'id', 'slug',
            'published_at', 'updated_at',
            'is_active',
            'content_type', 'object_id',
            'comment_target', 'reaction_target',
            'is_converted',
            'owner',
        ]

    # ---------------------------
    # OWNER (GFK)
    # ---------------------------
    def get_owner(self, obj):
        try:
            return build_owner_union_from_content_object(obj, context=self.context)
        except Exception as e:
            logger.exception("❌ VALIDATION ERROR: %s", e)
            logger.warning(
                "⚠️ get_owner failed for Testimony id=%s: %s",
                getattr(obj, "id", None), e
            )
            return None

    # ---------------------------
    # VALIDATION
    # ---------------------------
    def validate(self, attrs):
        logger.error("🔍 VALIDATE attrs = %s | instance=%s | context=%s", attrs, self.instance, self.context)
        instance = self.instance
        ttype = attrs.get('type') or (
            instance.type if instance else None
        ) or self.context.get('ttype')

        title = attrs.get('title') or (instance.title if instance else None)
        content = attrs.get('content') or (instance.content if instance else None)
        audio = attrs.get('audio') or (instance.audio if instance else None)
        video = attrs.get('video') or (instance.video if instance else None)

        # --- Written ---
        if ttype == Testimony.TYPE_WRITTEN:
            if not content or audio or video:
                raise serializers.ValidationError(
                    "Written testimony requires content and no audio/video."
                )
            if not title or not str(title).strip():
                raise serializers.ValidationError({"title": "Title is required."})
            if len(str(title)) > 50:
                raise serializers.ValidationError({"title": "Max 50 characters."})

        # --- Audio ---
        elif ttype == Testimony.TYPE_AUDIO:
            if not audio or content or video:
                raise serializers.ValidationError(
                    "Audio testimony requires audio only."
                )

        # --- Video ---
        elif ttype == Testimony.TYPE_VIDEO:
            if not video or content or audio:
                raise serializers.ValidationError(
                    "Video testimony requires video only."
                )

        else:
            raise serializers.ValidationError("Invalid testimony type.")

        attrs['type'] = ttype
        return attrs

    # ---------------------------
    #   CREATE
    # ---------------------------
    def create(self, validated_data):
        """
        Do NOT override content_type/object_id.
        Owner (GFK) must be set by the ViewSet.
        """
        logger.error("🧩 CREATE validated_data = %s", validated_data)
        validated_data.pop('is_active', None)

        inst = Testimony.objects.create(**validated_data)

        try:
            logger.info(
                "✅ Testimony saved: id=%s type=%s slug=%s",
                inst.pk, inst.type, inst.slug
            )
        except Exception:
            logger.exception("Post-create debug failed")

        return inst

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

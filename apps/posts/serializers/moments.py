# apps/posts/serializers/moments.py

from rest_framework import serializers
from django.apps import apps

from apps.posts.models.moment import Moment
from common.file_handlers.media_mixins import (
    ImageFileMixin, VideoFileMixin, ThumbnailFileMixin
)
from common.serializers.targets import InstanceTargetMixin
from apps.posts.serializers.serializers_owner_min import build_owner_union_from_content_object
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



        
# MOMENTS serializers -----------------------------------------------------------------------
class MomentSerializer(
    InstanceTargetMixin,
    ImageFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
    serializers.ModelSerializer
):
    owner = serializers.SerializerMethodField(read_only=True)

    content_type = serializers.PrimaryKeyRelatedField(read_only=True)
    object_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Moment
        fields = [
            "id", "slug",
            "caption",
            "image", "video", "thumbnail",
            "published_at", "updated_at",
            "is_active", "is_converted",
            "comment_target", "reaction_target",
            "owner",
        ]
        read_only_fields = [
            "id", "slug",
            "published_at", "updated_at",
            "is_active", "is_converted",
            "comment_target", "reaction_target",
            "owner",
        ]

    def get_owner(self, obj):
        return build_owner_union_from_content_object(obj, context=self.context)

    def validate(self, attrs):
        image = attrs.get("image") or getattr(self.instance, "image", None)
        video = attrs.get("video") or getattr(self.instance, "video", None)

        if image and video:
            raise serializers.ValidationError(
                "Moment cannot contain both image and video."
            )
        if not image and not video:
            raise serializers.ValidationError(
                "Moment must contain image or video."
            )
        return attrs

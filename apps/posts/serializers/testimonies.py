# apps/posts/serializers/testimonies.py
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
import traceback
import logging

from apps.posts.models import (
    Reaction, Comment,
    Resource, ServiceEvent,
    Testimony, Moment, Pray, Announcement, Lesson, Preach, Worship,
    MediaContent, Library, Witness, Mission, Conference, FutureConference
)
from common.file_handlers.media_mixins import (
    AudioFileMixin, VideoFileMixin, ThumbnailFileMixin
)
from apps.profiles.models import Member
from apps.accounts.serializers import SimpleCustomUserSerializer
from apps.profilesOrg.serializers_min import SimpleOrganizationSerializer
from .serializers_owner_min import build_owner_union_from_content_object
from apps.posts.constants import REACTION_TYPE_CHOICES
from django.contrib.auth import get_user_model

# ✅ میکسین هدف‌های ایتمی (per-item targets)
from common.serializers.targets import InstanceTargetMixin

logger = logging.getLogger(__name__)
CustomUser = get_user_model()


# TESTIMONY serializers -----------------------------------------------------------------
class TestimonySerializer(
    InstanceTargetMixin,                 # ✅ اضافه شد: comment_target / reaction_target
    AudioFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
    serializers.ModelSerializer
):
    """Unified serializer for written/audio/video testimonies with GFK + Reaction support."""

    is_active = serializers.BooleanField(read_only=True)
    owner = serializers.SerializerMethodField(read_only=True)

    # ✅ Legacy (برای سازگاریِ قبلیِ Reactions/Comments)
    content_type = serializers.SerializerMethodField(read_only=True)
    object_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Testimony
        fields = [
            'id', 'slug',
            'type', 'title',
            'content', 'audio', 'video',
            'thumbnail', 'published_at', 'updated_at', 'is_active',

            # --- legacy targets (حفظِ رفتار قبلی) ---
            'content_type', 'object_id',

            # --- per-item targets (جدید/پیشنهادی برای فرانت) ---
            'comment_target', 'reaction_target',

            'is_converted', 'owner',
        ]
        read_only_fields = [
            'id', 'slug',
            'published_at', 'updated_at', 'is_active',
            'content_type', 'object_id',           # legacy
            'comment_target', 'reaction_target',   # per-item
            'is_converted', 'owner',
        ]

    # --- Legacy getters (بدون تغییر رفتاری) ---
    def get_object_id(self, obj):
        return getattr(obj, "object_id", None)

    def get_content_type(self, obj):
        """
        Return 'app_label.model' string used by Reaction API.
        Works for Member/Organization or standalone Testimony.
        Never raises.
        """
        try:
            # 1) منبع اصلی: فیلد GFK خود آبجکت
            if getattr(obj, "content_type_id", None):
                ct = getattr(obj, "content_type", None)
                if ct and getattr(ct, "app_label", None):
                    return f"{ct.app_label}.{ct.model}"

            # 2) تلاش از روی آبجکت مالک (member/org)
            target = getattr(obj, "content_object", None)
            if target is not None:
                try:
                    ct = ContentType.objects.get_for_model(target.__class__)
                    return f"{ct.app_label}.{ct.model}"
                except Exception as inner_e:
                    logger.warning(
                        "⚠️ Failed inner get_for_model for Testimony id=%s: %s",
                        getattr(obj, "id", None), inner_e
                    )

            # 3) آخرین پناه: خود مدل Testimony
            ct = ContentType.objects.get_for_model(obj.__class__)
            return f"{ct.app_label}.{ct.model}"

        except Exception:
            logger.error(
                "🔥 get_content_type failed for Testimony id=%s:\n%s",
                getattr(obj, "id", None), traceback.format_exc()
            )
            return None

    # --- Owner (بدون تغییر) ---
    def get_owner(self, obj):
        try:
            return build_owner_union_from_content_object(obj, context=self.context)
        except Exception as e:
            logger.warning("⚠️ get_owner failed for Testimony id=%s: %s", getattr(obj, "id", None), e)
            return None

    # --- Validation (بدون تغییر منطقی) ---
    def validate(self, attrs):
        instance = self.instance
        ttype = attrs.get('type') or (instance.type if instance else None) or self.context.get('ttype')

        title = attrs.get('title') if 'title' in attrs else (instance.title if instance else None)
        content = attrs.get('content') if 'content' in attrs else (instance.content if instance else None)
        audio = attrs.get('audio') if 'audio' in attrs else (instance.audio if instance else None)
        video = attrs.get('video') if 'video' in attrs else (instance.video if instance else None)

        if ttype == Testimony.TYPE_WRITTEN:
            if not content or audio or video:
                raise serializers.ValidationError("Written testimony requires content and no audio/video.")
            if not title or not str(title).strip():
                raise serializers.ValidationError({"title": "Title is required for written testimony."})
            if len(str(title)) > 50:
                raise serializers.ValidationError({"title": "Max 50 characters."})

        elif ttype == Testimony.TYPE_AUDIO:
            if not audio or content or video:
                raise serializers.ValidationError("Audio testimony requires an audio file and no text/video.")

        elif ttype == Testimony.TYPE_VIDEO:
            if not video or content or audio:
                raise serializers.ValidationError("Video testimony requires a video file and no text/audio.")

        else:
            raise serializers.ValidationError("Invalid or missing testimony type.")

        attrs['type'] = ttype
        return attrs

    # --- Create (همان رفتار قبلی + setdefault با context) ---
    def create(self, validated_data):
        validated_data.setdefault('type', self.context.get('ttype'))
        validated_data.setdefault('content_type', self.context.get('content_type'))
        validated_data.setdefault('object_id', self.context.get('object_id'))
        validated_data.pop('is_active', None)

        inst = Testimony.objects.create(**validated_data)
        try:
            exists_now = Testimony.objects.filter(pk=inst.pk).exists()
            logger.info(
                "✅ Testimony saved: id=%s type=%s slug=%s (exists_now=%s, db_alias=%s)",
                inst.pk,
                inst.type,
                inst.slug,
                exists_now,
                getattr(inst._state, "db", None),
            )
        except Exception:
            logger.exception("Post-create existence check failed for id=%s", inst.pk)

        return inst

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

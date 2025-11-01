from rest_framework import serializers
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
import traceback
from .models import ( 
                Reaction, Comment,
                Resource, ServiceEvent,
                Testimony, Moment, Pray, Announcement, Lesson, Preach, Worship, MediaContent, Library, Witness, Mission, Conference, FutureConference
            )
from common.file_handlers.media_mixins import (
                AudioFileMixin, VideoFileMixin, ThumbnailFileMixin
            )
from apps.profiles.models import Member
from apps.accounts.serializers import SimpleCustomUserSerializer
from apps.profilesOrg.serializers_min import SimpleOrganizationSerializer
from .serializers_owner_min import build_owner_union_from_content_object
from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# BASE REACTION Serializer ---------------------------------------------------------------------
class ReactionSerializer(serializers.ModelSerializer):
    """
    Serializer for Reaction model.
    Supports flexible content_type input: "testimony", "posts.testimony", or numeric id.
    """

    # write-only input fields
    content_type = serializers.CharField(write_only=True)
    object_id = serializers.IntegerField()
    reaction_type = serializers.ChoiceField(choices=[c[0] for c in REACTION_TYPE_CHOICES])
    message = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=80)

    # read-only output fields
    id = serializers.IntegerField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)
    name = serializers.SerializerMethodField(read_only=True)
    content_type_label = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Reaction
        fields = [
            'id',
            'name',
            'reaction_type',
            'message',
            'content_type',
            'object_id',
            'timestamp',
            'content_type_label',
        ]
        read_only_fields = ['id', 'name', 'timestamp', 'content_type_label']

    # --- READ helpers ---
    def get_name(self, obj):
        """Return minimal user info for front-end."""
        u = obj.name
        return {'id': u.id, 'username': getattr(u, 'username', None)}

    def get_content_type_label(self, obj):
        """Return lowercased model name for readability."""
        return obj.content_type.model

    # --- INTERNAL helper: resolve CT string to object ---
    def _resolve_content_type(self, raw: str) -> ContentType:
        """
        Supports:
        - numeric id
        - 'app_label.model'
        - plain model name (scans installed apps)
        """
        raw = str(raw).strip()

        # numeric id
        if raw.isdigit():
            return ContentType.objects.get(pk=int(raw))

        # 'app_label.model'
        if '.' in raw:
            app_label, model = raw.split('.', 1)
            return ContentType.objects.get(app_label=app_label, model=model)

        # bare model name
        ct = ContentType.objects.filter(model=raw).first()
        if ct:
            return ct

        # fallback: brute-force scan across all installed apps
        for m in apps.get_models():
            if m._meta.model_name == raw:
                return ContentType.objects.get_for_model(m)

        raise serializers.ValidationError({'content_type': 'Invalid content type'})

    # --- VALIDATION ---
    def validate(self, attrs):
        # resolve ContentType
        ct = self._resolve_content_type(attrs['content_type'])
        attrs['content_type'] = ct

        # ensure target object exists
        model_class = ct.model_class()
        if not model_class.objects.filter(pk=attrs['object_id']).exists():
            raise serializers.ValidationError({'object_id': 'Target object not found'})

        # normalize empty message to None
        msg = attrs.get('message')
        if msg is not None and msg.strip() == '':
            attrs['message'] = None

        return attrs

    # --- CREATE ---
    def create(self, validated_data):
        """Assign current user as `name` (actor) automatically."""
        user = self.context['request'].user
        validated_data['name'] = user
        return Reaction.objects.create(**validated_data)


# COMMENT Serializers --------------------------------------------------------------------------
class SimpleCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'name', 'comment', 'published_at']

class CommentSerializer(serializers.ModelSerializer):
    responses = serializers.SerializerMethodField()
    content_type = serializers.SlugRelatedField(slug_field='model', queryset=ContentType.objects.all())

    class Meta:
        model = Comment
        fields = ['id', 'name', 'comment', 'published_at', 'content_type', 'object_id', 'responses']

    def get_responses(self, obj):
        # Fetch and serialize only one level of responses
        responses = obj.responses.all()  # Get all responses (re-comments) for the current comment
        return SimpleCommentSerializer(responses, many=True).data if responses.exists() else None
    

# RESOURCE Serializer ----------------------------------------------------------------------------
class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = '__all__'
        read_only_fields = ['uploaded_at','is_active']


# SERVICE EVENT Serializer ----------------------------------------------------------------------------
class ServiceEventSerializer(serializers.ModelSerializer):
    # location = serializers.SlugRelatedField(slug_field='full_address', queryset=Address.objects.all(), allow_null=True)
    class Meta:
        model = ServiceEvent
        fields = '__all__'
        read_only_fields = ['custom_name', 'get_event_type_choices','is_active']


# TESTIMONY serializers -----------------------------------------------------------------
class TestimonySerializer(AudioFileMixin, VideoFileMixin, ThumbnailFileMixin, serializers.ModelSerializer):
    """Unified serializer for written/audio/video testimonies with GFK + Reaction support."""

    is_active = serializers.BooleanField(read_only=True)
    owner = serializers.SerializerMethodField(read_only=True)

    # ✅ For Reactions system
    content_type = serializers.SerializerMethodField(read_only=True)
    object_id = serializers.SerializerMethodField(read_only=True)


    class Meta:
        model = Testimony
        fields = [
            'id', 'slug',
            'type', 'title',
            'content', 'audio', 'video',
            'thumbnail', 'published_at', 'updated_at', 'is_active',
            'content_type', 'object_id',
            'is_converted', 'owner',
        ]
        read_only_fields = [
            'id', 'slug',
            'published_at', 'updated_at', 'is_active',
            'content_type', 'object_id',
            'is_converted', 'owner',
        ]

    def get_object_id(self, obj):
        return getattr(obj, "object_id", None)
    
    # ✅ Safely serialize "app.model" string for Reaction API
    def get_content_type(self, obj):
        """
        Return 'app_label.model' string used by Reaction API.
        Works for Member/Organization or standalone Testimony.
        Never raises.
        """
        try:
            # 1️⃣ Primary source: GFK content_type field itself
            if getattr(obj, "content_type_id", None):
                ct = getattr(obj, "content_type", None)
                if ct and getattr(ct, "app_label", None):
                    return f"{ct.app_label}.{ct.model}"

            # 2️⃣ If linked object exists (e.g., member or org)
            target = getattr(obj, "content_object", None)
            if target is not None:
                try:
                    ct = ContentType.objects.get_for_model(target.__class__)
                    return f"{ct.app_label}.{ct.model}"
                except Exception as inner_e:
                    logger.warning("⚠️ Failed inner get_for_model for Testimony id=%s: %s", getattr(obj, "id", None), inner_e)

            # 3️⃣ Fallback: model itself (Testimony)
            ct = ContentType.objects.get_for_model(obj.__class__)
            return f"{ct.app_label}.{ct.model}"

        except Exception as e:
            logger.error("🔥 get_content_type failed for Testimony id=%s:\n%s", getattr(obj, "id", None), traceback.format_exc())
            return None

    # ✅ Safe owner builder (never crashes)
    def get_owner(self, obj):
        try:
            return build_owner_union_from_content_object(obj, context=self.context)
        except Exception as e:
            logger.warning("⚠️ get_owner failed for Testimony id=%s: %s", getattr(obj, "id", None), e)
            return None

    # ✅ Validation logic (unchanged)
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

    # ✅ Create with context defaults
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
        
# WITNESS serializers -----------------------------------------------------------------
class WitnessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Witness
        fields = [
            'id', 'title', 'testimony', 're_published_at',
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['re_published_at', 'is_active', 'slug']

        
# MOMENTS serializers -----------------------------------------------------------------------
class MomentSerializer(serializers.ModelSerializer):
    org_tags = SimpleOrganizationSerializer(many=True, read_only=True)
    user_tags = SimpleCustomUserSerializer(many=True, read_only=True)
    
    class Meta:
        model = Moment
        fields = [
            'id', 'content', 'moment_file', 'org_tags', 'user_tags',
            'published_at', 'updated_at', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['published_at', 'updated_at', 'is_active', 'slug']


# PRAY serializers -----------------------------------------------------------------
class PraySerializer(serializers.ModelSerializer):
    sub_prays = serializers.SerializerMethodField()

    class Meta:
        model = Pray
        fields = [
            'id', 'title', 'content', 'image', 'parent', 'sub_prays',
            'published_at', 'updated_at', 'is_accepted', 'is_rejected',
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['published_at', 'updated_at', 'is_active', 'slug']

    def get_sub_prays(self, obj):
        # Fetch and serialize sub-prays
        if obj.sub_prays.exists():
            return PraySerializer(obj.sub_prays.all(), many=True).data
        return None


# ANNOUNCEMENT serializers -----------------------------------------------------------------
class AnnouncementSerializer(serializers.ModelSerializer):
    # location = serializers.SlugRelatedField(slug_field='address', read_only=True)
    
    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'description', 'image', 'meeting_type', 'url_link', 'link_sticker_text', 
            'location', 'to_date', 'created_at', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['created_at', 'is_active', 'slug']

    def validate(self, data):
        # Custom validation for date fields
        if data['to_date'] and data['created_at'] and data['to_date'] <= data['created_at']:
            raise serializers.ValidationError("Date of Announcement must be after Created Date")
        return data


# LESSON serializers -----------------------------------------------------------------

class LessonSerializer(serializers.ModelSerializer):
    in_town_teachers = SimpleCustomUserSerializer(many=True, read_only=True)
    sub_lessons = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'season', 'episode', 'in_town_teachers', 'out_town_teachers', 'description', 
            'image', 'audio', 'video', 'parent', 'sub_lessons', 'view', 'record_date',
            'published_at', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'published_at', 'view', 'is_active', 'slug']

    def get_sub_lessons(self, obj):
        # Fetch and serialize sub-lessons
        if obj.sub_lessons.exists():
            return LessonSerializer(obj.sub_lessons.all(), many=True).data
        return None


# PREACH serializers -----------------------------------------------------------------
class PreachSerializer(serializers.ModelSerializer):
    in_town_preacher = SimpleCustomUserSerializer(read_only=True)

    class Meta:
        model = Preach
        fields = [
            'id', 'title', 'in_town_preacher', 'out_town_preacher', 'image', 'video',
            'view', 'published_at', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'view', 'published_at', 'is_active', 'slug']
    
    def get_profile_image(self, obj):
        # Returns full URL of image
        request = self.context.get('request')
        if obj.image:
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


# WORSHIP serializers -----------------------------------------------------------------
class WorshipSerializer(serializers.ModelSerializer):
    in_town_leaders = SimpleCustomUserSerializer(many=True, read_only=True)
    sub_worship = serializers.SerializerMethodField()

    class Meta:
        model = Worship
        fields = [
            'id', 'title', 'season', 'episode', 'sermon', 'hymn_lyrics', 
            'in_town_leaders', 'out_town_leaders', 'worship_resources', 
            'image', 'audio', 'video', 'parent', 'sub_worship', 'view', 
            'published_at', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'view', 'published_at', 'is_active', 'slug']

    def get_sub_worship(self, obj):
        # Fetch and serialize sub-worships
        if obj.sub_worship.exists():
            return WorshipSerializer(obj.sub_worship.all(), many=True).data
        return None

# MEDIA CONTENT serializers -----------------------------------------------------------------

class MediaContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaContent
        fields = [
            'id', 'content_type', 'title', 'description', 'file', 'link', 
            'published_at', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'published_at', 'is_active', 'slug']
    
    def get_file_url(self, obj):
        """Returns full URL of media file."""
        request = self.context.get('request')
        if obj.file:
            return request.build_absolute_uri(obj.file.url) if request else obj.file.url
        return None



# LIBRARY serializers -----------------------------------------------------------------
class LibrarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Library
        fields = [
            'id', 'book_name', 'author', 'publisher_name', 'language', 'translation_language', 'translator', 
            'genre_type', 'image', 'pdf_file', 'license_type', 'sale_status', 'license_document',
            'is_upcoming', 'is_downloadable', 'has_print_version', 'downloaded', 'published_date', 
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'downloaded', 'published_date', 'is_active', 'slug']

    def get_file_url(self, obj):
        """Returns full URL of the PDF file."""
        request = self.context.get('request')
        if obj.pdf_file:
            return request.build_absolute_uri(obj.pdf_file.url) if request else obj.pdf_file.url
        return None



# MISSION serializers -----------------------------------------------------------------
class MissionSerializer(serializers.ModelSerializer):
    contact_persons = SimpleCustomUserSerializer(many=True, read_only=True)
    
    class Meta:
        model = Mission
        fields = [
            'id', 'image_or_video', 'mission_name', 'description', 'start_date', 'end_date', 
            'is_ongoing', 'location', 'contact_persons', 'funding_goal', 'raised_funds', 'funding_link', 
            'volunteer_opportunities', 'mission_report', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'is_ongoing', 'slug']

    def get_image_or_video_url(self, obj):
        """Returns full URL of the image or video file."""
        request = self.context.get('request')
        if obj.image_or_video:
            return request.build_absolute_uri(obj.image_or_video.url) if request else obj.image_or_video.url
        return None


# CONFERENCES serializers -----------------------------------------------------------------
class ConferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conference
        fields = [
            'id', 'conference_name', 'workshops', 'conference_resources', 'description', 
            'conference_date', 'conference_time', 'conference_end_date', 
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active','slug']


# FUTURE CONFERENCES serializers -----------------------------------------------------------------
class FutureConferenceSerializer(serializers.ModelSerializer):
    in_town_speakers = SimpleCustomUserSerializer(many=True, read_only=True)
    sponsors = SimpleOrganizationSerializer(many=True, read_only=True)

    class Meta:
        model = FutureConference
        fields = [
            'id', 'conference_name', 'registration_required', 'delivery_type', 'conference_location', 
            'registration_link', 'conference_description', 'in_town_speakers', 'out_town_speakers', 
            'sponsors', 'conference_date', 'conference_time', 'conference_end_date', 
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']


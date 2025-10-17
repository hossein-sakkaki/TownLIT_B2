from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
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

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# BASE REACTION Serializer ---------------------------------------------------------------------
class ReactionSerializer(serializers.ModelSerializer):
    content_type = serializers.SlugRelatedField(slug_field='model', queryset=ContentType.objects.all())
    class Meta:
        model = Reaction
        fields = ['id', 'name', 'reaction_type', 'message', 'content_type', 'object_id', 'timestamp']
    
    def create(self, validated_data):
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
    is_active = serializers.BooleanField(read_only=True)
    owner = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Testimony
        fields = [
            'id','slug','type','title','content',
            'audio','video','thumbnail',
            'published_at','updated_at','is_active',
            'content_type','object_id','is_converted',
            'owner',
        ]
        read_only_fields = [
            'published_at','updated_at','is_converted','slug',
            'content_type','object_id','is_active',
            'owner',
        ]

    # Build a small, public owner union from GFK
    def get_owner(self, obj):
        # Ensure request in context for absolute URLs
        return build_owner_union_from_content_object(obj, context=self.context)


    # serializers.py
    def validate(self, attrs):
        instance = self.instance
        ttype = attrs.get('type') or (instance.type if instance else None) or self.context.get('ttype')

        title   = attrs.get('title')   if 'title'   in attrs else (instance.title   if instance else None)
        content = attrs.get('content') if 'content' in attrs else (instance.content if instance else None)
        audio   = attrs.get('audio')   if 'audio'   in attrs else (instance.audio   if instance else None)
        video   = attrs.get('video')   if 'video'   in attrs else (instance.video   if instance else None)

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

    def create(self, validated_data):
        validated_data.setdefault('type', self.context.get('ttype'))
        validated_data.setdefault('content_type', self.context.get('content_type'))
        validated_data.setdefault('object_id', self.context.get('object_id'))
        validated_data.pop('is_active', None)
        inst = Testimony.objects.create(**validated_data)
        try:
            exists_now = Testimony.objects.filter(pk=inst.pk).exists()
            logger.info("✅ Testimony saved: id=%s type=%s slug=%s (exists_now=%s, db_alias=%s)",
                        inst.pk, inst.type, inst.slug, exists_now, getattr(inst._state, "db", None))
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


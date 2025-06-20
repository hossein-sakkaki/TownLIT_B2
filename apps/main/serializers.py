from rest_framework import serializers
from django.utils.timesince import timesince
from django.utils import timezone

from common.aws.s3_utils import get_file_url
from .models import (
    TermsAndPolicy, UserAgreement, PolicyChangeHistory, 
    FAQ, UserFeedback, SiteAnnouncement, UserActionLog,
    Prayer,
    VideoCategory, VideoSeries, OfficialVideo, VideoViewLog
    )



# TERMS AND POLICY Serializer ---------------------------------------------------------------------------------
class TermsAndPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = TermsAndPolicy
        fields = '__all__'


# USER AGREEMENT Serializer -----------------------------------------------------------------------------------
class UserAgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAgreement
        fields = '__all__'


# POLICY CHANGE HISTORY Serializer ----------------------------------------------------------------------------
class PolicyChangeHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyChangeHistory
        fields = '__all__'


# FAQ Serializer ----------------------------------------------------------------------------------------------
class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = '__all__'


# USER FEEDBACK Serializer ------------------------------------------------------------------------------------
class UserFeedbackSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = UserFeedback
        fields = ['id', 'user', 'title', 'content', 'screenshot', 'status', 'created_at']
        read_only_fields = ['id', 'user', 'status', 'created_at']



# SITE ANNOUNCEMENT Serializer --------------------------------------------------------------------------------
class SiteAnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteAnnouncement
        fields = '__all__'


# USER ACTION LOG Serializer ----------------------------------------------------------------------------------
class UserActionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActionLog
        fields = '__all__'
        

# PRAYER Serializer -----------------------------------------------------------------------------------------------
class PrayerSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField(read_only=True)
    company_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Prayer
        fields = [
            'id', 'user',  'full_name', 'email',  'content', 'allow_display',
            'admin_response',  'responded_by', 'responded_at',  'is_active',  'submitted_at', 'display_name',
            "company_name",
        ]
        read_only_fields = [
            'user', 'admin_response',  'responded_by', 'responded_at',
            'is_active', 'submitted_at', 'display_name'
        ]

    def get_display_name(self, obj):
        if obj.user:
            return f"{obj.user.name} {obj.user.family}".strip() or obj.user.username
        return obj.full_name or "Guest"

    def create(self, validated_data):
        validated_data.pop('company_name', None)
        
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['user'] = user
        return super().create(validated_data)


# VIDEO CATEGORY Serializer -----------------------------------------------------------------------------------------
class VideoCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoCategory
        fields = ['id', 'name', 'description', 'is_active']
        
class VideoSeriesSerializer(serializers.ModelSerializer):
    intro_video_id = serializers.PrimaryKeyRelatedField(
        source="intro_video", queryset=OfficialVideo.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = VideoSeries
        fields = [
            "id", "title", "description", "language",
            "is_active", "created_at", "slug", "intro_video_id"
        ]
        
        
# Official Video Serializer -------------------------------------
class OfficialVideoSerializer(serializers.ModelSerializer):
    category = VideoCategorySerializer(read_only=True)
    series = VideoSeriesSerializer(read_only=True)
    time_since_publish = serializers.SerializerMethodField()
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent", queryset=OfficialVideo.objects.all(), required=False, allow_null=True
    )
    children_count = serializers.SerializerMethodField()

    video_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    video_file_path = serializers.SerializerMethodField()

    class Meta:
        model = OfficialVideo
        fields = [
            'id', 'title', 'description', 'language',
            'category', 'series', 'episode_number',
            'video_url', 'thumbnail_url', 'video_file_path', 'view_count',
            'is_active', 'publish_date', 'created_at', 'slug',
            'time_since_publish', 'parent_id', 'children_count',
            'is_converted',
        ]

    def get_time_since_publish(self, obj):
        return timesince(obj.publish_date, timezone.now()) if obj.publish_date else None

    def get_children_count(self, obj):
        return obj.children.count()

    def get_video_url(self, obj):
        return get_file_url(str(obj.video_file.name)) if obj.video_file else None

    def get_video_file_path(self, obj):
        path = str(obj.video_file.name) if obj.video_file else None
        print("✅ [get_video_file_path CALLED] =>", path)
        return path

    def get_thumbnail_url(self, obj):
        return get_file_url(str(obj.thumbnail.name)) if obj.thumbnail else None
    

class OfficialVideoCreateUpdateSerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(queryset=OfficialVideo.objects.all(), required=False, allow_null=True)

    class Meta:
        model = OfficialVideo
        fields = [
            'title', 'description', 'language', 'category',
            'series', 'parent', 'episode_number', 'video_file',
            'thumbnail', 'is_active', 'publish_date'
        ]

class VideoViewLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoViewLog
        fields = ['id', 'video', 'ip_address', 'user_agent', 'viewed_at']
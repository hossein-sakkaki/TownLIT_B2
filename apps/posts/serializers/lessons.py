from rest_framework import serializers
from django.apps import apps
from apps.posts.models import Lesson
from apps.accounts.serializers import SimpleCustomUserSerializer 
from apps.profilesOrg.serializers_min import SimpleOrganizationSerializer

from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



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

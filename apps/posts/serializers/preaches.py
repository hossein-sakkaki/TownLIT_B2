from rest_framework import serializers
from django.apps import apps
from apps.posts.models import Preach
from apps.accounts.serializers import SimpleCustomUserSerializer 
from apps.profilesOrg.serializers_min import SimpleOrganizationSerializer

from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



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








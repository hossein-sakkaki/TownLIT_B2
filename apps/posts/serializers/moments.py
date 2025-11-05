from rest_framework import serializers
from django.apps import apps
from apps.posts.models import Moment
from apps.accounts.serializers import SimpleCustomUserSerializer 
from apps.profilesOrg.serializers_min import SimpleOrganizationSerializer
            
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



        
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


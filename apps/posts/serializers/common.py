from rest_framework import serializers
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from apps.posts.models.common import Resource

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# RESOURCE Serializer ----------------------------------------------------------------------------
class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = '__all__'
        read_only_fields = ['uploaded_at','is_active']



        

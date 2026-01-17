from rest_framework import serializers
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from apps.posts.models.common import Resource
from rest_framework.serializers import ListSerializer

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



        
# FILTER NONE LIST Serializer ---------------------------------------------------------------------
class FilterNoneListSerializer(ListSerializer):
    """
    Removes None items returned by child.to_representation
    """
    def to_representation(self, data):
        iterable = data.all() if hasattr(data, "all") else data
        result = []
        for item in iterable:
            rep = self.child.to_representation(item)
            if rep is not None:
                result.append(rep)
        return result
    

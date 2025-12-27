from rest_framework import serializers
from django.apps import apps
from apps.posts.models.service_event import ServiceEvent
            

from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()




# SERVICE EVENT Serializer ----------------------------------------------------------------------------
class ServiceEventSerializer(serializers.ModelSerializer):
    # location = serializers.SlugRelatedField(slug_field='full_address', queryset=Address.objects.all(), allow_null=True)
    class Meta:
        model = ServiceEvent
        fields = '__all__'
        read_only_fields = ['custom_name', 'get_event_type_choices','is_active']

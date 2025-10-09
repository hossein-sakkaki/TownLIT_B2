from rest_framework import serializers
from .models import Organization


# SIMPLE ORGANIZATION Serializer ------------------------------------------------------------------- 
class SimpleOrganizationSerializer(serializers.ModelSerializer):
    organization_logo = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ['id', 'org_name', 'organization_logo', 'slug']
        read_only_fields = ['id','slug']

    def get_organization_logo(self, obj):
        request = self.context.get('request')
        if obj.logo:
            return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url
        return None
    

    
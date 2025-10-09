from rest_framework import serializers
from .models import Member


# SIMPLE MEMBER Serializers ------------------------------------------------------------------------    
class SimpleMemberSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()
    class Meta:
        model = Member
        fields = ['id', 'profile_image','slug']
        read_only_fields = ['id', 'slug']
        
    def get_profile_image(self, obj):
        request = self.context.get('request')
        if obj.id.image_name:
            return request.build_absolute_uri(obj.id.image_name.url) if request else obj.id.image_name.url
        return None

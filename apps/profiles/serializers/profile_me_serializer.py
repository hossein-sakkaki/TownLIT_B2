# apps/profiles/serializers/profile_me_serializer.py

from rest_framework import serializers


class ProfileMeSerializer(serializers.Serializer):
    profile_type = serializers.CharField()
    profile_id = serializers.IntegerField(allow_null=True)
    username = serializers.CharField()
    is_member = serializers.BooleanField()
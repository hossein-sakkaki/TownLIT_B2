from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType

from apps.accounts.models.social import SocialMediaLink, SocialMediaType
from apps.profilesOrg.models import Organization


# SOCIAL MEDIA LINK Serializers ---------------------------------------------------------------
# Media Types Serializer
class SocialMediaTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialMediaType
        fields = ['id', 'name', 'icon_class', 'icon_svg', 'is_active']


# Media Link Serializer
class SocialMediaLinkSerializer(serializers.ModelSerializer):
    social_media_type = serializers.PrimaryKeyRelatedField(
        queryset=SocialMediaType.objects.filter(is_active=True)
    )
    content_type = serializers.CharField(write_only=True)
    object_id = serializers.IntegerField(write_only=True)
    content_object = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SocialMediaLink
        fields = ['id', 'social_media_type', 'link', 'content_type', 'object_id', 'content_object', 'is_active']
        
    def validate(self, data):
        content_type = data.get('content_type')
        object_id = data.get('object_id')
        social_media_type = data.get('social_media_type')
        link = data.get('link')

        if not content_type or not object_id:
            raise serializers.ValidationError(
                {"error": "Both content_type and object_id are required."}
            )
        try:
            content_type_model = ContentType.objects.get(model=content_type).model_class()
            if content_type_model == Organization:
                if not Organization.objects.filter(id=object_id, org_owners=self.context['request'].user).exists():
                    raise serializers.ValidationError(
                        {"error": "You do not have permission to add or modify links for this organization."}
                    )
            elif content_type_model != self.context['request'].user.__class__:
                raise serializers.ValidationError({"error": "Invalid content_type or object_id provided."})
        except ContentType.DoesNotExist:
            raise serializers.ValidationError({"error": "Invalid content_type provided."})

        existing_link = SocialMediaLink.objects.filter(
            content_type__model=content_type,
            object_id=object_id,
            social_media_type=social_media_type
        ).first()
        if existing_link:
            raise serializers.ValidationError(
                {"error": "A link for this social media type already exists."}
            )

        if SocialMediaLink.objects.filter(link=link).exists():
            raise serializers.ValidationError(
                {"error": "This URL is already in use."}
            )
        return data

    def create(self, validated_data):
        content_type = validated_data.pop('content_type')
        object_id = validated_data.pop('object_id')

        try:
            content_type_instance = ContentType.objects.get(model=content_type)
            validated_data['content_type'] = content_type_instance
            validated_data['object_id'] = object_id
            return super().create(validated_data)
        except ContentType.DoesNotExist:
            raise serializers.ValidationError({"error": "Invalid content_type provided."})

    def get_content_object(self, obj):
        if isinstance(obj.content_object, Organization):
            return {"type": "organization", "name": obj.content_object.org_name}
        elif obj.content_object == self.context['request'].user:
            return {"type": "user", "username": obj.content_object.username}
        return None


# Read Only Media Link Serializer
class SocialMediaLinkReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer for displaying a list of social media links with nested
    social media type details.
    """
    social_media_type = SocialMediaTypeSerializer(read_only=True)
    content_object = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SocialMediaLink
        fields = ['id', 'social_media_type', 'link', 'content_object', 'is_active']

    def get_content_object(self, obj):
        if isinstance(obj.content_object, Organization):
            return {"type": "organization", "name": obj.content_object.org_name}
        elif obj.content_object == self.context['request'].user:
            return {"type": "user", "username": obj.content_object.username}
        return None

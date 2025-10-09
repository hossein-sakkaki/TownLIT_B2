from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from .models import (
                Address, CustomLabel, SocialMediaType, SocialMediaLink,
                UserDeviceKey,
                InviteCode
            )
from apps.profiles.models import Member
from apps.profilesOrg.models import Organization
from validators.user_validators import validate_email_field, validate_password_field
from common.file_handlers.profile_image import ProfileImageMixin

import logging
from django.contrib.auth import get_user_model

CustomUser = get_user_model()
logger = logging.getLogger(__name__)


# LOGIN Serializer ----------------------------------------------------------------------
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(validators=[validate_email_field])
    password = serializers.CharField(write_only=True, validators=[validate_password_field])

    
# REGISTER USER Serializer ---------------------------------------------------------------
class RegisterUserSerializer(serializers.ModelSerializer):
    agree_to_terms = serializers.BooleanField(write_only=True)
    invite_code = serializers.CharField(write_only=True, required=False, allow_blank=True)
    email = serializers.EmailField()
    
    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'agree_to_terms', 'invite_code']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate_email(self, value):
        existing_user = CustomUser.objects.filter(email__iexact=value).first()
        if existing_user and existing_user.is_active:
            raise serializers.ValidationError(
                "A user with this email already exists. Please log in or use a different email address."
            )
        return value

    def validate(self, data):
        if not data.get('agree_to_terms'):
            raise serializers.ValidationError(
                "To join our community, we kindly ask you to agree to the terms and conditions. It’s how we care for one another in love and trust."
            )

        if getattr(settings, 'USE_INVITE_CODE', False):
            invite_code = data.get('invite_code')
            if not invite_code:
                raise serializers.ValidationError({
                    "invite_code": "An invite code is needed to continue. If you haven’t received one, feel free to reach out — we’re here for you!"
                })

            try:
                invite = InviteCode.objects.get(code=invite_code)
            except InviteCode.DoesNotExist:
                raise serializers.ValidationError({
                    "invite_code": "This invite code doesn’t seem to be valid. Please double-check or contact us if you need help."
                })

            if invite.is_used:
                raise serializers.ValidationError({
                    "invite_code": "This invite code has already been used. If you need a new one, we’d be glad to assist!"
                })

            email = data.get('email')
            if invite.email and invite.email.lower() != email.lower():
                raise serializers.ValidationError({
                    "invite_code": "This code was sent for a different email. If you believe this is an error, please let us know — we’re happy to help."
                })

            self.invite = invite

        return data


# VERIFY NEWBORN CODE Serializer -------------------------------------------------------------
class VerifyNewBornSerializer(serializers.Serializer):
    active_code = serializers.CharField(max_length=5)  # Adjust the max length as needed

    def validate_active_code(self, value):
        if not value.isdigit() or len(value) != 5:
            raise serializers.ValidationError("Invalid active code format")

        return value
    
# FORGET & RESET PASSWORD Serializer ---------------------------------------------------------
class ForgetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    
class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(max_length=128, write_only=True)

    def validate_new_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("The new password must be at least 8 characters long.")
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError("The new password must contain at least one digit.")
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError("The new password must contain at least one uppercase letter.")
        if not any(char.islower() for char in value):
            raise serializers.ValidationError("The new password must contain at least one lowercase letter.")
        return value

# CHANGE PASSWORD Serializer -----------------------------------------------------------------
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_new_password = serializers.CharField(required=True, write_only=True)

    def validate_old_password(self, value):
        # Chech Old Password
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("The old password is incorrect.")
        return value

    def validate_new_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("The new password must be at least 8 characters long.")
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError("The new password must contain at least one digit.")
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError("The new password must contain at least one uppercase letter.")
        if not any(char.islower() for char in value):
            raise serializers.ValidationError("The new password must contain at least one lowercase letter.")
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError("The new password and the confirmation password do not match.")
        return attrs


# ADDRESS Serializers ------------------------------------------------------------------------
class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'

# LABEL Serializers --------------------------------------------------------------------------
class CustomLabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomLabel
        fields = '__all__'

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


# CustomUser Serializers -----------------------------------------------------------------------
class CustomUserSerializer(ProfileImageMixin, serializers.ModelSerializer):
    label = CustomLabelSerializer(read_only=True)
    is_verified_identity = serializers.SerializerMethodField()
    country = serializers.CharField(write_only=True)
    country_display = serializers.CharField(
        source='get_country_display', read_only=True
    )
    primary_language_display = serializers.CharField(
        source='get_primary_language_display', read_only=True
    )
    secondary_language_display = serializers.CharField(
        source='get_secondary_language_display', read_only=True
    )
    
    class Meta:
        model = CustomUser
        exclude = ['registration_id', 'access_pin', 'delete_pin', 'is_active', 'is_admin', 'is_deleted', 'reports_count',
                   'is_superuser', 'is_suspended', 'reactivated_at', 'deletion_requested_at', 'email_change_tokens',
                   'reset_token', 'reset_token_expiration', 'register_date', 'mobile_verification_code', 'mobile_verification_expiry', 'user_active_code', 'user_active_code_expiry',
                ]        
        read_only_fields = ['id', 'register_date', ]
        extra_kwargs = {
            'password': {'write_only': True},
            'username': {
                'validators': []
            }
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
        instance.generate_rsa_keys()
        instance.save()
        return instance

    def update(self, instance, validated_data):
        # Remove sensitive fields
        password = validated_data.pop('password', None)
        validated_data.pop('is_active', None)
        profile_image = validated_data.pop('profile_image', None)

        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Hash and set the password if it's provided
        if password is not None:
            instance.set_password(password)
            
        if profile_image:
            instance.image_name = profile_image 

        instance.save()
        return instance
    
    def validate_username(self, value):
        # Check if the username is unchanged
        if self.instance and value == self.instance.username:
            return value  
        if CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("Unfortunately, this username is already taken. Please choose another one.")
        return value

    def get_is_verified_identity(self, obj):
        return getattr(getattr(obj, 'member_profile', None), 'is_verified_identity', False)
    
    
# CustomUser Public Serializers -----------------------------------------------------------------------
class PublicCustomUserSerializer(ProfileImageMixin, serializers.ModelSerializer):
    label = CustomLabelSerializer(read_only=True)
    is_verified_identity = serializers.SerializerMethodField()
    country_display = serializers.CharField(source='get_country_display', read_only=True)
    primary_language_display = serializers.CharField(source='get_primary_language_display', read_only=True)
    secondary_language_display = serializers.CharField(source='get_secondary_language_display', read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'name', 'family', 'username', 'gender', 'label', 'is_verified_identity',
            'country', 'country_display',
            'primary_language', 'primary_language_display',
            'secondary_language', 'secondary_language_display',
            'email', 'mobile_number',
            'city', 'birthday',
            'show_email', 'show_phone_number', 'show_country', 'show_city',
            'registration_started_at', 
            'is_account_paused', 'is_suspended'
        ]
        read_only_fields = fields  # visitor is read-only

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # honor privacy flags on CustomUser
        if not getattr(instance, 'show_email', False):
            rep.pop('email', None)
        if not getattr(instance, 'show_phone_number', False):
            rep.pop('mobile_number', None)
        if not getattr(instance, 'show_country', False):
            rep.pop('country', None)
            rep.pop('country_display', None)
        if not getattr(instance, 'show_city', False):
            rep.pop('city', None)
        return rep

    def get_is_verified_identity(self, obj):
        return getattr(getattr(obj, 'member_profile', None), 'is_verified_identity', False)


    
# LIMITED MEMBER Serializer ------------------------------------------------------------------------------
class LimitedCustomUserSerializer(ProfileImageMixin, serializers.ModelSerializer):
    """
    Ultra-minimal public view of CustomUser.
    """
    label = CustomLabelSerializer(read_only=True)
    is_verified_identity = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'id', 'name', 'family', 'username', 'gender', 'label',
            'is_verified_identity', 'is_member', 'is_suspended', 'is_account_paused'
        ]
        read_only_fields = fields

    def get_is_verified_identity(self, obj):
        # Derive from related member profile if any
        return getattr(getattr(obj, 'member_profile', None), 'is_verified_identity', False)




# Simple CustomUser Serializers For Showing Users ------------------------------------------------
class SimpleCustomUserSerializer(ProfileImageMixin, serializers.ModelSerializer):
    label = CustomLabelSerializer(read_only=True)
    is_friend = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    is_verified_identity = serializers.SerializerMethodField()
    
    request_sent = serializers.SerializerMethodField()
    has_received_request = serializers.SerializerMethodField()
    friendship_id = serializers.SerializerMethodField()
    fellowship_id = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
                'id', 'username', 'name', 'family', 'label', 
                'is_friend', 'request_sent', 'has_received_request', 'friendship_id', 'fellowship_id',
                'profile_url', 'is_verified_identity'
            ]
        read_only_fields = ['id']

    def get_is_friend(self, obj):
        friend_ids = self.context.get('friend_ids', set())
        return obj.id in friend_ids

    def get_request_sent(self, obj):
        sent_map = self.context.get('sent_request_map', {})
        return obj.id in sent_map

    def get_has_received_request(self, obj):
        received_map = self.context.get('received_request_map', {})
        return obj.id in received_map

    def get_friendship_id(self, obj):
        received_map = self.context.get('received_request_map', {})
        if obj.id in received_map:
            return received_map[obj.id]

        sent_map = self.context.get('sent_request_map', {})
        if obj.id in sent_map:
            return sent_map[obj.id]

        return None

    def get_fellowship_id(self, obj):
        return self.context.get('fellowship_ids', {}).get(obj.id)

    def get_profile_url(self, obj):
        if not isinstance(obj, CustomUser):
            return None
        return obj.get_absolute_url()

    def get_is_verified_identity(self, obj):
        return getattr(getattr(obj, 'member_profile', None), 'is_verified_identity', False)


# Reactivation User Serializers -----------------------------------------------------------------------
class ReactivationUserSerializer(serializers.ModelSerializer):
    """
    Minimal payload for reactivation flow.
    No PII beyond email/username. No profile/label/locale.
    """
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'email',
            'username',
            'is_member',
            'is_deleted',
            'deletion_requested_at',
            # optional hints for FE UX:
            'two_factor_enabled',
        ]
        read_only_fields = fields


# User Device Key Serializers -----------------------------------------------------------------------
class UserDeviceKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDeviceKey
        fields = [
            'device_id', 'device_name', 'user_agent', 'ip_address',
            'created_at', 'last_used', 'is_active',
            "location_city", "location_region", "location_country",
            "is_verified", "verified_at"
        ]
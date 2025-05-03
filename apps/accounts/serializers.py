from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from .models import (
                Address, CustomLabel, SocialMediaType, SocialMediaLink,
                OrganizationService, 
                SpiritualService,
                UserDeviceKey,
                InviteCode
            )
from apps.profilesOrg.models import Organization
from common.validators import validate_email_field, validate_password_field
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
    invite_code = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'agree_to_terms', 'invite_code']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if not data.get('agree_to_terms'):
            raise serializers.ValidationError("You must agree to the terms and conditions.")

        if getattr(settings, 'USE_INVITE_CODE', False):
            invite_code = data.get('invite_code')
            if not invite_code:
                raise serializers.ValidationError({"invite_code": "An invite code is required."})
            try:
                invite = InviteCode.objects.get(code=invite_code)
            except InviteCode.DoesNotExist:
                raise serializers.ValidationError({"invite_code": "Invalid invite code."})

            if invite.is_used:
                raise serializers.ValidationError({"invite_code": "This invite code has already been used."})

            email = data.get('email')
            if invite.email and invite.email.lower() != email.lower():
                raise serializers.ValidationError({"invite_code": "This invite code is not valid for this email address."})

            self.invite = invite

        return data

    def create(self, validated_data):
        validated_data.pop('agree_to_terms')
        invite_code = validated_data.pop('invite_code', None)

        user = CustomUser.objects.create_user(
            email=validated_data['email']
        )
        if not user.image_name:
            user.image_name = settings.DEFAULT_PROFILE_IMAGE

        user.set_password(validated_data['password'])
        user.save()

        # اگر invite تعریف شده بود، آن را استفاده‌شده علامت بزن
        if getattr(settings, 'USE_INVITE_CODE', False):
            self.invite.mark_as_used(user)

        return user
    
# class RegisterUserSerializer(serializers.ModelSerializer):
#     agree_to_terms = serializers.BooleanField(write_only=True)

#     class Meta:
#         model = CustomUser
#         fields = ['email', 'password', 'agree_to_terms']
#         extra_kwargs = {
#             'password': {'write_only': True}
#         }

#     def validate(self, data):
#         if not data.get('agree_to_terms'):
#             raise serializers.ValidationError("You must agree to the terms and conditions.")
#         return data

#     def create(self, validated_data):
#         # Remove `agree_to_terms` before creating the user
#         validated_data.pop('agree_to_terms')
#         user = CustomUser.objects.create_user(
#             email=validated_data['email']
#         )
#         if not user.image_name:
#             user.image_name = settings.DEFAULT_PROFILE_IMAGE

#         user.set_password(validated_data['password'])
#         user.save()
#         return user


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

    def validate_email(self, value):
        try:
            user = CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("This email does not exist in our system.")
        return value
    
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


# ORGANIZATION SERVICE CATEGORY Serializers ---------------------------------------------------
class OrganizationServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationService
        fields = '__all__'
        read_only_fields = ['id','is_active']


# MEMBER SERVICE TYPE Serializers -------------------------------------------------------------
class SpiritualServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpiritualService
        fields = '__all__'
        read_only_fields = ['id','is_active']


# CustomUser Serializers -----------------------------------------------------------------------
class CustomUserSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()
    label = CustomLabelSerializer(read_only=True)
    country_display = serializers.CharField(source='get_country_display', read_only=True)
    country = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        exclude = ['registration_id', 'access_pin', 'delete_pin', 'is_active', 'is_admin', 'is_deleted', 'reports_count',
                   'is_superuser', 'is_suspended', 'reactivated_at', 'deletion_requested_at',
                   'reset_token', 'reset_token_expiration', 'register_date', 'mobile_verification_code', 'mobile_verification_expiry', 'user_active_code', 'user_active_code_expiry',
                ]        
        read_only_fields = ['id', 'register_date', ]
        extra_kwargs = {
            'password': {'write_only': True},
            'username': {
                'validators': []
            }
        }

    def create(self, instance, validated_data):
        password = validated_data.pop('password', None)
        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
        # Generate RSA keys for the user upon creation
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
    
    def get_profile_image_url(self, obj):
        request = self.context.get('request')
        if obj.image_name and obj.image_name.url:
            return request.build_absolute_uri(obj.image_name.url) if request else obj.image_name.url
        default_image_path = settings.MEDIA_URL + 'sample/user.png'
        return request.build_absolute_uri(default_image_path) if request else default_image_path
    
    def validate_username(self, value):
        # Check if the username is unchanged
        if self.instance and value == self.instance.username:
            return value  # Username has not changed
        if CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("Unfortunately, this username is already taken. Please choose another one.")
        return value

    
# CustomUser Public Serializers -----------------------------------------------------------------------
class PublicCustomUserSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = [
            'email', 'mobile_number', 'name', 'family', 'username', 'birthday', 
            'gender', 'label', 'profile_image_url', 'country',
            'primary_language', 'secondary_language', 'is_active', 'is_member', 'is_suspended'
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # حذف مقادیر بر اساس show_* flags
        if not getattr(instance, 'show_email', False):
            representation.pop('email', None)
        if not getattr(instance, 'show_phone_number', False):
            representation.pop('mobile_number', None)
        if not getattr(instance, 'show_country', False):
            representation.pop('country', None)
        if not getattr(instance, 'show_city', False):
            representation.pop('city', None)
        return representation

    def get_profile_image_url(self, obj):
        request = self.context.get('request')
        if obj.image_name and obj.image_name.url:
            return request.build_absolute_uri(obj.image_name.url) if request else obj.image_name.url
        default_image_path = settings.MEDIA_URL + 'sample/user.png'
        return request.build_absolute_uri(default_image_path) if request else default_image_path

    
# LIMITED MEMBER Serializer ------------------------------------------------------------------------------
class LimitedCustomUserSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'name', 'family', 'username',
            'gender', 'label', 'profile_image_url',
            'primary_language', 'secondary_language', 'is_member',
        ]
        
    def get_profile_image_url(self, obj):
        request = self.context.get('request')
        if obj.image_name and obj.image_name.url:
            return request.build_absolute_uri(obj.image_name.url) if request else obj.image_name.url
        default_image_path = settings.MEDIA_URL + 'sample/user.png'
        return request.build_absolute_uri(default_image_path) if request else default_image_path


# Simple CustomUser Serializers For Showing Users ------------------------------------------------
class SimpleCustomUserSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()
    is_friend = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'name', 'family', 'profile_image', 'is_friend', 'profile_url']
        read_only_fields = ['id']

    def get_profile_image(self, obj):             # ------------------- باید حل شود + پایین تر
        if not isinstance(obj, CustomUser):
            return None
        request = self.context.get('request')
        if obj.image_name:
            return request.build_absolute_uri(obj.image_name.url) if request else obj.image_name.url
        return None

    def get_is_friend(self, obj):
        if not isinstance(obj, CustomUser):
            return False
        friend_ids = self.context.get('friend_ids', set())
        return obj.id in friend_ids
    
    # def get_profile_url(self, obj):
    #     return obj.get_absolute_url()
    
    def get_profile_url(self, obj):              # ------------------- باید حل شود + بالا تر
        if not isinstance(obj, CustomUser):
            return None
        return obj.get_absolute_url()
    

# User Device Key Serializers -----------------------------------------------------------------------
class UserDeviceKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDeviceKey
        fields = [
            'device_id',
            'device_name',
            'user_agent',
            'ip_address',
            'created_at',
            'last_used',
            'is_active'
        ]


# apps/accounts/serializers.py
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from django.conf import settings
from .models import (
                Address, CustomLabel, SocialMediaType, SocialMediaLink,
                UserDeviceKey,
                InviteCode,
                IdentityVerification,
                LITShieldGrant
            )
from .mixins import AvatarURLMixin
from apps.profilesOrg.models import Organization
from validators.user_validators import validate_email_field, validate_password_field
from rest_framework.reverse import reverse
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


# -------------------------------------------------------------------
# CustomUserSerializer — Full editable profile (for owner only)
# -------------------------------------------------------------------
class CustomUserSerializer(AvatarURLMixin, serializers.ModelSerializer):
    # --- Label + color ---
    label = CustomLabelSerializer(read_only=True)
    label_color = serializers.CharField(source="label.color", read_only=True)

    # --- Identity verification ---
    is_verified_identity = serializers.BooleanField(read_only=True)
    is_townlit_verified = serializers.SerializerMethodField()

    # --- LitShield access ---
    has_litshield_access = serializers.SerializerMethodField()

    # --- Display enums ---
    country_display = serializers.CharField(source='get_country_display', read_only=True)
    primary_language_display = serializers.CharField(source='get_primary_language_display', read_only=True)
    secondary_language_display = serializers.CharField(source='get_secondary_language_display', read_only=True)

    # --- Profile URL (detail page) ---
    profile_url = serializers.SerializerMethodField()

    # --- Avatar proxy (FAST, no S3 signing on frontend) ---
    avatar_url = serializers.SerializerMethodField()
    avatar_version = serializers.IntegerField(read_only=True)

    # country = write_only field
    country = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CustomUser

        # ⚠️ IMPORTANT:
        # exclude dangerous internal fields but keep profile-related fields.
        exclude = [
            'registration_id', 'access_pin', 'delete_pin', 'is_active',
            'is_admin', 'is_deleted', 'reports_count', 'is_superuser',
            'is_suspended', 'reactivated_at', 'deletion_requested_at',
            'email_change_tokens', 'reset_token', 'reset_token_expiration',
            'mobile_verification_code', 'mobile_verification_expiry',
            'user_active_code', 'user_active_code_expiry',
        ]

        read_only_fields = ['id', 'register_date']

        extra_kwargs = {
            'password': {'write_only': True},
            'username': {
                'validators': []  # username uniqueness manually validated
            }
        }

    # --------------------------------------------------------------------
    # CREATE USER
    # --------------------------------------------------------------------
    def create(self, validated_data):
        password = validated_data.pop('password', None)

        instance = CustomUser(**validated_data)

        if password:
            instance.set_password(password)

        # Generate RSA keys for E2EE system
        instance.generate_rsa_keys()

        instance.save()
        return instance

    # --------------------------------------------------------------------
    # UPDATE USER (owner updates their profile)
    # --------------------------------------------------------------------
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)

        # Non-editable fields
        validated_data.pop('is_active', None)
        validated_data.pop('is_admin', None)
        validated_data.pop('is_superuser', None)

        # Handle avatar change
        profile_image = validated_data.pop('profile_image', None)

        # Update normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        # ⬅️ Avatar changed?
        if profile_image:
            instance.image_name = profile_image
            instance.avatar_version = (instance.avatar_version or 1) + 1

        instance.save()
        return instance


    # --------------------------------------------------------------------
    # VALIDATE USERNAME
    # --------------------------------------------------------------------
    def validate_username(self, value):
        if self.instance and value == self.instance.username:
            return value
        if CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "Unfortunately, this username is already taken. Please choose another one."
            )
        return value

    def get_profile_url(self, obj):
        try:
            return obj.get_absolute_url()
        except Exception:
            return None

    # --------------------------------------------------------------------
    # Fast avatar proxy URL
    # --------------------------------------------------------------------
    def get_avatar_url(self, obj):
        return self.build_avatar_url(obj)

    # --------------------------------------------------------------------
    # Is TownLIT verified?
    # --------------------------------------------------------------------
    def get_is_townlit_verified(self, obj):
        """
        Derived flag:
        True if user has a member profile AND it is TownLIT verified.
        """
        mp = getattr(obj, "member_profile", None)
        return bool(mp and mp.is_townlit_verified)

    # --------------------------------------------------------------------
    # LitShield access?
    # --------------------------------------------------------------------
    def get_has_litshield_access(self, obj):
        """
        Security permission flag (LITShield):
        True ONLY if an active LITShieldGrant exists.
        Independent from identity or spiritual verification.
        """
        return LITShieldGrant.objects.filter(user=obj, is_active=True).exists()


    
     
# -------------------------------------------------------------------
# PublicCustomUserSerializer — full public profile, with avatar_url
# -------------------------------------------------------------------
class PublicCustomUserSerializer(AvatarURLMixin, serializers.ModelSerializer):
    label = CustomLabelSerializer(read_only=True)
    label_color = serializers.CharField(source="label.color", read_only=True)

    # verification + profile URL
    is_verified_identity = serializers.BooleanField(read_only=True)
    is_townlit_verified = serializers.SerializerMethodField()

    profile_url = serializers.SerializerMethodField()

    # display-friendly enums
    country_display = serializers.CharField(source='get_country_display', read_only=True)
    primary_language_display = serializers.CharField(source='get_primary_language_display', read_only=True)
    secondary_language_display = serializers.CharField(source='get_secondary_language_display', read_only=True)

    # NEW: fast avatar proxy URL
    avatar_url = serializers.SerializerMethodField()
    avatar_version = serializers.IntegerField(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            # identity
            "id", "name", "family", "username", "gender",

            # label system
            "label", "label_color",

            # verification
            "is_verified_identity",
            "is_townlit_verified",

            # location + languages
            "country", "country_display",
            "primary_language", "primary_language_display",
            "secondary_language", "secondary_language_display",
            "city", "birthday",

            # contact fields
            "email", "mobile_number",

            # visibility flags
            "show_email", "show_phone_number",
            "show_country", "show_city",

            # account state
            "registration_started_at",
            "is_account_paused", "is_suspended",

            # UI routing
            "profile_url",
            "avatar_url",
            "avatar_version",
        ]
        read_only_fields = fields  # Pure output serializer

    # -------------------------------------------------------
    # PRIVACY FILTER
    # -------------------------------------------------------
    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # respect privacy flags
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


    def get_profile_url(self, obj):
        try:
            return obj.get_absolute_url()
        except Exception:
            return None

    def get_avatar_url(self, obj):
        return self.build_avatar_url(obj)

    def get_is_townlit_verified(self, obj):
        """
        Derived flag:
        True if user has a member profile AND it is TownLIT verified.
        """
        mp = getattr(obj, "member_profile", None)
        return bool(mp and mp.is_townlit_verified)





# -------------------------------------------------------------------
# LimitedCustomUserSerializer — very small footprint
# -------------------------------------------------------------------
class LimitedCustomUserSerializer(AvatarURLMixin, serializers.ModelSerializer):
    label = CustomLabelSerializer(read_only=True)
    label_color = serializers.CharField(source="label.color", read_only=True)
    is_verified_identity = serializers.BooleanField(read_only=True)
    is_townlit_verified = serializers.SerializerMethodField()

    profile_url = serializers.SerializerMethodField()

    # NEW: avatar proxy URL
    avatar_url = serializers.SerializerMethodField()
    avatar_version = serializers.IntegerField(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "name",
            "family",
            "username",
            "gender",

            "label",
            "label_color",

            "is_verified_identity",
            "is_townlit_verified",
            
            "is_member",
            "is_suspended",
            "is_account_paused",

            # NEW:
            "profile_url",
            "avatar_url",
            "avatar_version",
        ]
        read_only_fields = fields


    def get_profile_url(self, obj):
        try:
            return obj.get_absolute_url()
        except Exception:
            return None

    def get_avatar_url(self, obj):
        return self.build_avatar_url(obj)

    def get_is_townlit_verified(self, obj):
        """
        Derived flag:
        True if user has a member profile AND it is TownLIT verified.
        """
        mp = getattr(obj, "member_profile", None)
        return bool(mp and mp.is_townlit_verified)



 
# Simple CustomUser Serializers For Showing Users ------------------------------------------------
class SimpleCustomUserSerializer(AvatarURLMixin, serializers.ModelSerializer):
    # --- Label / badge ---
    label = CustomLabelSerializer(read_only=True)
    label_color = serializers.CharField(source="label.color", read_only=True)

    # --- Friendship / fellowship state ---
    is_friend = serializers.SerializerMethodField()
    request_sent = serializers.SerializerMethodField()
    has_received_request = serializers.SerializerMethodField()
    friendship_id = serializers.SerializerMethodField()
    fellowship_id = serializers.SerializerMethodField()

    # --- Profile + verification ---
    profile_url = serializers.SerializerMethodField()
    is_verified_identity = serializers.BooleanField(read_only=True)
    is_townlit_verified = serializers.SerializerMethodField()

    # --- NEW: avatar proxy URL (no S3 signing on frontend) ---
    avatar_url = serializers.SerializerMethodField()
    avatar_version = serializers.IntegerField(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id", 
            "username",
            "name",
            "family",

            # badge + label
            "label",
            "label_color",

            # friend/fellowship states
            "is_friend",
            "request_sent",
            "has_received_request",
            "friendship_id", 
            "fellowship_id",

            # profile link
            "profile_url",

            # verification flag
            "is_verified_identity",
            "is_townlit_verified",

            # avatar proxy (fast)
            "avatar_url",
            "avatar_version",
        ]
        read_only_fields = ["id"]

    # ---------------------------------------------------------------
    # Friendship state fields
    # ---------------------------------------------------------------

    def get_is_friend(self, obj):
        """
        True if this user is already in the caller's friends set.
        friend_ids: set of user IDs passed via context.
        """
        friend_ids = self.context.get("friend_ids", set())
        return obj.id in friend_ids

    def get_request_sent(self, obj):
        """
        True if current user has sent a pending request to 'obj'.
        sent_request_map: { to_user_id: friendship_id }
        """
        sent_map = self.context.get("sent_request_map", {})
        return obj.id in sent_map

    def get_has_received_request(self, obj):
        """
        True if current user has *received* a pending request from 'obj'.
        received_request_map: { from_user_id: friendship_id }
        """
        received_map = self.context.get("received_request_map", {})
        return obj.id in received_map

    def get_friendship_id(self, obj):
        """
        Legacy numeric ID of the Friendship edge (if any).
        Frontend uses this when calling delete-friendships.
        Priority:
          1) incoming requests (received_map)
          2) outgoing requests (sent_map)
        """
        received_map = self.context.get("received_request_map", {})
        if obj.id in received_map:
            return received_map[obj.id]

        sent_map = self.context.get("sent_request_map", {})
        if obj.id in sent_map:
            return sent_map[obj.id]

        # For plain friends_list / suggestions you can also
        # inject direct { user_id: friendship_id } map in context
        direct_map = self.context.get("friendship_ids", {})
        if obj.id in direct_map:
            return direct_map[obj.id]

        return None

    def get_fellowship_id(self, obj):
        """
        Optional: map of { user_id: fellowship_id } passed via context.
        Used in covenant/fellowship screens.
        """
        return self.context.get("fellowship_ids", {}).get(obj.id)

    # ---------------------------------------------------------------
    # Profile URL
    # ---------------------------------------------------------------
    def get_profile_url(self, obj):
        """
        Stable profile URL for user (detail page).
        Uses model's get_absolute_url for flexibility.
        """
        if not isinstance(obj, CustomUser):
            return None
        try:
            return obj.get_absolute_url()
        except Exception:
            return None

    # ---------------------------------------------------------------
    # Avatar Proxy URL (FAST)
    # ---------------------------------------------------------------
    def get_avatar_url(self, obj):
        return self.build_avatar_url(obj)

    # ---------------------------------------------------------------
    # TownLIT verification
    # ---------------------------------------------------------------
    def get_is_townlit_verified(self, obj):
        """
        Derived flag:
        True if user has a member profile AND it is TownLIT verified.
        """
        mp = getattr(obj, "member_profile", None)
        return bool(mp and mp.is_townlit_verified)


            

# ------------------------------------------------------------------------------------
class UserMiniSerializer(AvatarURLMixin, serializers.ModelSerializer):
    is_verified_identity = serializers.BooleanField(read_only=True)
    is_townlit_verified = serializers.SerializerMethodField()

    label_color = serializers.CharField(source='label.color', read_only=True)

    avatar_url = serializers.SerializerMethodField()
    avatar_version = serializers.IntegerField(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "name",
            "family",
            "is_verified_identity",
            "is_townlit_verified",
            "label_color",
            "avatar_url", "avatar_version",
        ]


    def get_avatar_url(self, obj):
        return self.build_avatar_url(obj)

    def get_is_townlit_verified(self, obj):
        """
        Derived flag:
        True if user has a member profile AND it is TownLIT verified.
        """
        mp = getattr(obj, "member_profile", None)
        return bool(mp and mp.is_townlit_verified)




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


# FCM Token Serializers -----------------------------------------------------------------------
class DevicePushTokenSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=100)
    push_token = serializers.CharField(max_length=512)
    platform = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def save(self, user):
        device_id = self.validated_data["device_id"]
        push_token = self.validated_data["push_token"]
        platform = self.validated_data.get("platform") or "web"

        obj, created = UserDeviceKey.objects.get_or_create(
            user=user,
            device_id=device_id,
            defaults={
                "platform": platform,
                "push_token": push_token,
            },
        )

        if not created:
            obj.platform = platform
            obj.push_token = push_token
            obj.is_active = True
            obj.last_used = timezone.now()
            obj.save(update_fields=["platform", "push_token", "is_active", "last_used"])

        return obj



# Identity Serializers -----------------------------------------------------------------------
class IdentityStartSerializer(serializers.Serializer):
    # Start identity verification
    success_url = serializers.URLField(required=False)
    failure_url = serializers.URLField(required=False)


class IdentityStatusSerializer(serializers.ModelSerializer):
    # Identity status for UI
    class Meta:
        model = IdentityVerification
        fields = (
            "method",
            "status",
            "level",
            "verified_at",
            "revoked_at",
            "rejected_at",
            "risk_flag",
        )


class IdentityRevokeSerializer(serializers.Serializer):
    # Manual revoke by admin
    reason = serializers.CharField(max_length=1000, required=False)


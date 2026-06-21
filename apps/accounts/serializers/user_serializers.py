# accounts/serializers/user_serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.accounts.serializers.label_serializers import CustomLabelSerializer
from apps.accounts.services.age_policy import validate_standard_account_birthday
from ..mixins import AvatarURLMixin
from ..models import CustomLabel, LITShieldGrant
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.accounts.models.username_reservation import UsernameReservation
from validators.usernameValidators.username_validator import validate_username_format

CustomUser = get_user_model()


# -------------------------------------------------------------------
# CustomUserAuthSerializer — Source of Truth for Auth
# -------------------------------------------------------------------
class CustomUserAuthSerializer(AvatarURLMixin, serializers.ModelSerializer):
    # --- Label + color ---
    label = CustomLabelSerializer(read_only=True)
    label_color = serializers.SerializerMethodField()

    # --- Identity flags ---
    is_verified_identity = serializers.BooleanField(read_only=True)
    is_townlit_verified = serializers.SerializerMethodField()
    has_litshield_access = serializers.SerializerMethodField()

    # --- Display helpers ---
    primary_language_display = serializers.CharField(
        source="get_primary_language_display",
        read_only=True
    )
    secondary_language_display = serializers.CharField(
        source="get_secondary_language_display",
        read_only=True
    )
    country_display = serializers.CharField(
        source="get_country_display",
        read_only=True
    )

    # --- Avatar ---
    avatar_url = serializers.SerializerMethodField()
    avatar_cdn_url = serializers.SerializerMethodField()
    avatar_version = serializers.IntegerField(read_only=True)

    # --- Navigation ---
    profile_url = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "name",
            "family",

            "label",
            "label_color",

            "is_member",
            "is_verified_identity",
            "is_townlit_verified",
            "has_litshield_access",

            "two_factor_enabled",
            "pin_security_enabled",
            "is_account_paused",
            "is_suspended",

            "primary_language",
            "primary_language_display",
            "secondary_language",
            "secondary_language_display",
            "country_display",

            "avatar_url",
            "avatar_cdn_url",
            "avatar_version",

            "profile_url",
            "groups",
        ]

        read_only_fields = fields  # 🔐 HARD READ-ONLY

    # --------------------------------------------------
    def get_profile_url(self, obj):
        return obj.get_absolute_url()

    def get_avatar_url(self, obj):
        return self.build_avatar_url(obj)

    def get_avatar_cdn_url(self, obj):
        return self.build_avatar_cdn_url(obj)

    def get_is_townlit_verified(self, obj):
        mp = getattr(obj, "member_profile", None)
        return bool(mp and mp.is_townlit_verified)

    def get_has_litshield_access(self, obj):
        return LITShieldGrant.objects.filter(
            user=obj,
            is_active=True
        ).exists()

    def get_label_color(self, obj):
        if obj.label:
            return obj.label.color
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
    avatar_cdn_url = serializers.SerializerMethodField()
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
        old_username = instance.username

        password = validated_data.pop('password', None)

        validated_data.pop('is_active', None)
        validated_data.pop('is_admin', None)
        validated_data.pop('is_superuser', None)

        profile_image = validated_data.pop('profile_image', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        if profile_image:
            instance.image_name = profile_image
            instance.avatar_version = (instance.avatar_version or 1) + 1

        instance.save()

        if old_username and instance.username != old_username:
            UsernameReservation.reserve(old_username, instance)

        return instance


    # --------------------------------------------------------------------
    # VALIDATE BIRTHDAY / AGE POLICY
    # --------------------------------------------------------------------
    def validate_birthday(self, value):
        """
        Standard TownLIT accounts currently require age 13+.

        This validation is intentionally placed on CustomUserSerializer because
        birthday belongs to CustomUser but is updated through nested Member/Guest
        profile serializers.
        """
        return validate_standard_account_birthday(value)

    # --------------------------------------------------------------------
    # VALIDATE USERNAME
    # --------------------------------------------------------------------
    def validate_username(self, value):
        try:
            username = validate_username_format(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)

        if self.instance and username == self.instance.username:
            return username

        if UsernameReservation.is_reserved_for_other_user(username, self.instance):
            raise serializers.ValidationError(
                "This username was recently used by another account and is temporarily unavailable."
            )

        if CustomUser.objects.filter(username=username).exists():
            raise serializers.ValidationError(
                "This username is already taken by another account. Please choose a different username."
            )

        return username

    # --------------------------------------------------------------------
    # Profile URL
    # --------------------------------------------------------------------
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

    def get_avatar_cdn_url(self, obj):
        return self.build_avatar_cdn_url(obj)

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
    avatar_cdn_url = serializers.SerializerMethodField()
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
            "avatar_cdn_url",
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

    def get_avatar_cdn_url(self, obj):
        return self.build_avatar_cdn_url(obj)
    
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
    avatar_cdn_url = serializers.SerializerMethodField()
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
            "avatar_cdn_url",
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
    
    def get_avatar_cdn_url(self, obj):
        return self.build_avatar_cdn_url(obj)

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
    avatar_cdn_url = serializers.SerializerMethodField()
    avatar_version = serializers.IntegerField(read_only=True)

    # --- Mutual friends preview ---
    mutual_friends_count = serializers.SerializerMethodField()
    mutual_friends = serializers.SerializerMethodField()
    
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
            "avatar_cdn_url",
            "avatar_version",
            
            # mutual friends
            "mutual_friends_count",
            "mutual_friends",
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
    # Mutual friends preview
    # ---------------------------------------------------------------

    def get_mutual_friends_count(self, obj):
        """
        Count of mutual friends between request.user and this suggested user.

        Expected context:
          mutual_count_map: { suggested_user_id: count }
        """
        mutual_count_map = self.context.get("mutual_count_map", {})
        return int(mutual_count_map.get(obj.id, 0) or 0)

    def get_mutual_friends(self, obj):
        """
        Preview list of mutual friends.

        Expected context:
          mutual_preview_map: { suggested_user_id: [CustomUser, ...] }
        """
        mutual_preview_map = self.context.get("mutual_preview_map", {})
        mutual_users = mutual_preview_map.get(obj.id, [])

        return SimpleMutualFriendSerializer(
            mutual_users,
            many=True,
            context=self.context,
        ).data
        
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
    
    def get_avatar_cdn_url(self, obj):
        return self.build_avatar_cdn_url(obj)

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
    avatar_cdn_url = serializers.SerializerMethodField()
    avatar_version = serializers.IntegerField(read_only=True)

    # ✅ clickable profile link
    profile_url = serializers.SerializerMethodField()

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
            "avatar_url", "avatar_cdn_url", "avatar_version",
            "profile_url",
        ]

    def get_avatar_url(self, obj):
        return self.build_avatar_url(obj)

    def get_avatar_cdn_url(self, obj):
        return self.build_avatar_cdn_url(obj)

    def get_profile_url(self, obj):
        # ✅ TownLIT public profile route
        if getattr(obj, "username", None):
            return f"/lit/{obj.username}"
        return "/lit/"

    def get_is_townlit_verified(self, obj):
        mp = getattr(obj, "member_profile", None)
        return bool(mp and mp.is_townlit_verified)

# Compact serializer for mutual friends preview -----------------------------------------------
class SimpleMutualFriendSerializer(AvatarURLMixin, serializers.ModelSerializer):
    label_color = serializers.CharField(source="label.color", read_only=True)
    profile_url = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    avatar_cdn_url = serializers.SerializerMethodField()
    is_townlit_verified = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "label_color",
            "profile_url",
            "is_verified_identity",
            "is_townlit_verified",
            "avatar_url",
            "avatar_cdn_url",
        ]
        read_only_fields = ["id"]

    def get_profile_url(self, obj):
        try:
            return obj.get_absolute_url()
        except Exception:
            return None

    def get_avatar_url(self, obj):
        return self.build_avatar_url(obj)

    def get_avatar_cdn_url(self, obj):
        return self.build_avatar_cdn_url(obj)

    def get_is_townlit_verified(self, obj):
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


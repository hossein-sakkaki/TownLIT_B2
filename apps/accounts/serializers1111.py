# # apps/accounts/serializers.py
# from rest_framework import serializers
# from django.contrib.contenttypes.models import ContentType
# from django.utils import timezone

# from django.conf import settings
# from .models import (
#                 Address, CustomLabel, SocialMediaType, SocialMediaLink,
#                 UserDeviceKey,
#                 InviteCode,
#                 IdentityVerification,
#                 LITShieldGrant
#             )
# from .mixins import AvatarURLMixin
# from apps.profilesOrg.models import Organization
# from validators.user_validators import validate_email_field, validate_password_field 
# from rest_framework.reverse import reverse
# import logging
# from django.contrib.auth import get_user_model

# CustomUser = get_user_model()
# logger = logging.getLogger(__name__)


# # # LOGIN Serializer ----------------------------------------------------------------------
# # class LoginSerializer(serializers.Serializer):
# #     email = serializers.EmailField(validators=[validate_email_field])
# #     password = serializers.CharField(write_only=True, validators=[validate_password_field])

    
# # # REGISTER USER Serializer ---------------------------------------------------------------
# # class RegisterUserSerializer(serializers.ModelSerializer):
# #     agree_to_terms = serializers.BooleanField(write_only=True)
# #     invite_code = serializers.CharField(write_only=True, required=False, allow_blank=True)
# #     email = serializers.EmailField()
    
# #     class Meta:
# #         model = CustomUser
# #         fields = ['email', 'password', 'agree_to_terms', 'invite_code']
# #         extra_kwargs = {
# #             'password': {'write_only': True}
# #         }

# #     def validate_email(self, value):
# #         existing_user = CustomUser.objects.filter(email__iexact=value).first()
# #         if existing_user and existing_user.is_active:
# #             raise serializers.ValidationError(
# #                 "A user with this email already exists. Please log in or use a different email address."
# #             )
# #         return value

# #     def validate(self, data):
# #         if not data.get('agree_to_terms'):
# #             raise serializers.ValidationError(
# #                 "To join our community, we kindly ask you to agree to the terms and conditions. It’s how we care for one another in love and trust."
# #             )

# #         if getattr(settings, 'USE_INVITE_CODE', False):
# #             invite_code = data.get('invite_code')
# #             if not invite_code:
# #                 raise serializers.ValidationError({
# #                     "invite_code": "An invite code is needed to continue. If you haven’t received one, feel free to reach out — we’re here for you!"
# #                 })

# #             try:
# #                 invite = InviteCode.objects.get(code=invite_code)
# #             except InviteCode.DoesNotExist:
# #                 raise serializers.ValidationError({
# #                     "invite_code": "This invite code doesn’t seem to be valid. Please double-check or contact us if you need help."
# #                 })

# #             if invite.is_used:
# #                 raise serializers.ValidationError({
# #                     "invite_code": "This invite code has already been used. If you need a new one, we’d be glad to assist!"
# #                 })

# #             email = data.get('email')
# #             if invite.email and invite.email.lower() != email.lower():
# #                 raise serializers.ValidationError({
# #                     "invite_code": "This code was sent for a different email. If you believe this is an error, please let us know — we’re happy to help."
# #                 })

# #             self.invite = invite

# #         return data


# # # VERIFY NEWBORN CODE Serializer -------------------------------------------------------------
# # class VerifyNewBornSerializer(serializers.Serializer):
# #     active_code = serializers.CharField(max_length=5)  # Adjust the max length as needed

# #     def validate_active_code(self, value):
# #         if not value.isdigit() or len(value) != 5:
# #             raise serializers.ValidationError("Invalid active code format")

# #         return value
    
# # # FORGET & RESET PASSWORD Serializer ---------------------------------------------------------
# # class ForgetPasswordSerializer(serializers.Serializer):
# #     email = serializers.EmailField()

    
# # class ResetPasswordSerializer(serializers.Serializer):
# #     new_password = serializers.CharField(max_length=128, write_only=True)

# #     def validate_new_password(self, value):
# #         if len(value) < 8:
# #             raise serializers.ValidationError("The new password must be at least 8 characters long.")
# #         if not any(char.isdigit() for char in value):
# #             raise serializers.ValidationError("The new password must contain at least one digit.")
# #         if not any(char.isupper() for char in value):
# #             raise serializers.ValidationError("The new password must contain at least one uppercase letter.")
# #         if not any(char.islower() for char in value):
# #             raise serializers.ValidationError("The new password must contain at least one lowercase letter.")
# #         return value

# # # CHANGE PASSWORD Serializer -----------------------------------------------------------------
# # class ChangePasswordSerializer(serializers.Serializer):
# #     old_password = serializers.CharField(required=True, write_only=True)
# #     new_password = serializers.CharField(required=True, write_only=True)
# #     confirm_new_password = serializers.CharField(required=True, write_only=True)

# #     def validate_old_password(self, value):
# #         # Chech Old Password
# #         user = self.context['request'].user
# #         if not user.check_password(value):
# #             raise serializers.ValidationError("The old password is incorrect.")
# #         return value

# #     def validate_new_password(self, value):
# #         if len(value) < 8:
# #             raise serializers.ValidationError("The new password must be at least 8 characters long.")
# #         if not any(char.isdigit() for char in value):
# #             raise serializers.ValidationError("The new password must contain at least one digit.")
# #         if not any(char.isupper() for char in value):
# #             raise serializers.ValidationError("The new password must contain at least one uppercase letter.")
# #         if not any(char.islower() for char in value):
# #             raise serializers.ValidationError("The new password must contain at least one lowercase letter.")
# #         return value

# #     def validate(self, attrs):
# #         if attrs['new_password'] != attrs['confirm_new_password']:
# #             raise serializers.ValidationError("The new password and the confirmation password do not match.")
# #         return attrs


# # # ADDRESS Serializers ------------------------------------------------------------------------
# # class AddressSerializer(serializers.ModelSerializer):
# #     class Meta:
# #         model = Address
# #         fields = '__all__'

# # # LABEL Serializers --------------------------------------------------------------------------
# # class CustomLabelSerializer(serializers.ModelSerializer):
# #     class Meta:
# #         model = CustomLabel
# #         fields = '__all__'











# # # User Device Key Serializers -----------------------------------------------------------------------
# # class UserDeviceKeySerializer(serializers.ModelSerializer):
# #     class Meta:
# #         model = UserDeviceKey
# #         fields = [
# #             'device_id', 'device_name', 'user_agent', 'ip_address',
# #             'created_at', 'last_used', 'is_active',
# #             "location_city", "location_region", "location_country",
# #             "is_verified", "verified_at"
# #         ]


# # # FCM Token Serializers -----------------------------------------------------------------------
# # class DevicePushTokenSerializer(serializers.Serializer):
# #     device_id = serializers.CharField(max_length=100)
# #     push_token = serializers.CharField(max_length=512)
# #     platform = serializers.CharField(max_length=20, required=False, allow_blank=True)

# #     def save(self, user):
# #         device_id = self.validated_data["device_id"]
# #         push_token = self.validated_data["push_token"]
# #         platform = self.validated_data.get("platform") or "web"

# #         obj, created = UserDeviceKey.objects.get_or_create(
# #             user=user,
# #             device_id=device_id,
# #             defaults={
# #                 "platform": platform,
# #                 "push_token": push_token,
# #             },
# #         )

# #         if not created:
# #             obj.platform = platform
# #             obj.push_token = push_token
# #             obj.is_active = True
# #             obj.last_used = timezone.now()
# #             obj.save(update_fields=["platform", "push_token", "is_active", "last_used"])

# #         return obj



# # # Identity Serializers -----------------------------------------------------------------------
# # class IdentityStartSerializer(serializers.Serializer):
# #     # Start identity verification
# #     success_url = serializers.URLField(required=False)
# #     failure_url = serializers.URLField(required=False)


# # class IdentityStatusSerializer(serializers.ModelSerializer):
# #     # Identity status for UI
# #     class Meta:
# #         model = IdentityVerification
# #         fields = (
# #             "method",
# #             "status",
# #             "level",
# #             "verified_at",
# #             "revoked_at",
# #             "rejected_at",
# #             "risk_flag",
# #         )


# # class IdentityRevokeSerializer(serializers.Serializer):
# #     # Admin revoke payload
# #     reason = serializers.CharField(max_length=1000, required=False)
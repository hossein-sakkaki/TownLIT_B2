# apps/accounts/serializers/auth_serializers.py

from rest_framework import serializers
from django.conf import settings
from django.contrib.auth import get_user_model

from validators.user_validators import validate_email_field, validate_password_field
from ..models import InviteCode

CustomUser = get_user_model()


# LOGIN Serializer
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(validators=[validate_email_field])
    password = serializers.CharField(write_only=True, validators=[validate_password_field])


# REGISTER USER Serializer
class RegisterUserSerializer(serializers.ModelSerializer):
    agree_to_terms = serializers.BooleanField(write_only=True)
    invite_code = serializers.CharField(write_only=True, required=False, allow_blank=True)
    email = serializers.EmailField()

    class Meta:
        model = CustomUser
        fields = ["email", "password", "agree_to_terms", "invite_code"]
        extra_kwargs = {"password": {"write_only": True}}

    def validate_email(self, value):
        existing_user = CustomUser.objects.filter(email__iexact=value).first()
        if existing_user and existing_user.is_active:
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value

    def validate(self, data):

        if not data.get("agree_to_terms"):
            raise serializers.ValidationError(
                "You must agree to the terms and conditions."
            )

        if getattr(settings, "USE_INVITE_CODE", False):

            invite_code = data.get("invite_code")

            if not invite_code:
                raise serializers.ValidationError({"invite_code": "Invite code required."})

            try:
                invite = InviteCode.objects.get(code=invite_code)
            except InviteCode.DoesNotExist:
                raise serializers.ValidationError({"invite_code": "Invalid invite code."})

            if invite.is_used:
                raise serializers.ValidationError({"invite_code": "Invite code already used."})

            email = data.get("email")

            if invite.email and invite.email.lower() != email.lower():
                raise serializers.ValidationError({"invite_code": "Invite code email mismatch."})

            self.invite = invite

        return data


class VerifyNewBornSerializer(serializers.Serializer):
    active_code = serializers.CharField(max_length=5)

    def validate_active_code(self, value):
        if not value.isdigit() or len(value) != 5:
            raise serializers.ValidationError("Invalid active code format")
        return value


class ForgetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):

    new_password = serializers.CharField(max_length=128, write_only=True)

    def validate_new_password(self, value):

        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters.")

        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError("Password must contain a digit.")

        if not any(char.isupper() for char in value):
            raise serializers.ValidationError("Password must contain uppercase letter.")

        if not any(char.islower() for char in value):
            raise serializers.ValidationError("Password must contain lowercase letter.")

        return value


class ChangePasswordSerializer(serializers.Serializer):

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):

        user = self.context["request"].user

        if not user.check_password(value):
            raise serializers.ValidationError("Old password incorrect.")

        return value

    def validate(self, attrs):

        if attrs["new_password"] != attrs["confirm_new_password"]:
            raise serializers.ValidationError("Passwords do not match.")

        return attrs
# apps/profiles/serializers/profile_me_serializer.py

from rest_framework import serializers


class ProfileMeGateSerializer(serializers.Serializer):
    key = serializers.CharField(allow_null=True, required=False)
    reason = serializers.CharField(allow_null=True, required=False)
    redirect_to = serializers.CharField(allow_null=True, required=False)
    owner_message = serializers.CharField(allow_null=True, required=False)


class ProfileMeSerializer(serializers.Serializer):
    profile_type = serializers.CharField()
    profile_id = serializers.IntegerField(allow_null=True)
    username = serializers.CharField()
    is_member = serializers.BooleanField()

    # Lightweight owner-access gate for iOS shell/bootstrap.
    # Values:
    # - normal
    # - restricted
    # - missing
    owner_profile_access_mode = serializers.CharField()

    profile_gate = ProfileMeGateSerializer(allow_null=True, required=False)

    # Lightweight account flags. These are cheap fields already on user.
    is_account_paused = serializers.BooleanField()
    is_suspended = serializers.BooleanField()


# # apps/profiles/serializers/profile_me_serializer.py

# from rest_framework import serializers


# class ProfileMeSerializer(serializers.Serializer):
#     profile_type = serializers.CharField()
#     profile_id = serializers.IntegerField(allow_null=True)
#     username = serializers.CharField()
#     is_member = serializers.BooleanField()
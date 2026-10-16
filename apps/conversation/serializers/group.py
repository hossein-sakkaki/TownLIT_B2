# apps/conversation/serializers/group.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from validators.groupNames.group_name_validator import validate_group_name


class CreateGroupSerializer(serializers.Serializer):
    group_name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=60,
        trim_whitespace=True,
    )
    group_image = serializers.ImageField(
        required=False,
        allow_null=True,
    )

    def validate_group_name(self, value):
        try:
            return validate_group_name(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages[0])


class UpdateGroupInfoSerializer(serializers.Serializer):
    group_name = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=60,
        trim_whitespace=True,
    )

    def validate_group_name(self, value):
        try:
            return validate_group_name(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages[0])

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field must be provided.")
        return attrs

# apps/core/boundaries/serializers.py

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.core.boundaries.constants import (
    BOUNDARY_STILLNESS,
    BOUNDARY_BOUNDARY,
    BOUNDARY_TYPE_CHOICES,
    BOUNDARY_SOURCE_PROFILE,
    BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE,
)
from apps.core.boundaries.models import UserBoundary

CustomUser = get_user_model()


# ---------------------------------------------------------------------
# API-safe reason normalizer
# ---------------------------------------------------------------------
def boundary_unavailable_reason_to_text(
    value: Any,
    *,
    fallback: str | None = None,
) -> str | None:
    """
    Normalize Boundary/Stillness unavailable reason for public API responses.

    IMPORTANT:
    iOS expects `direct_interaction_unavailable_reason` to be String? .
    Never expose a dict/object for that field.

    Accepts:
    - None
    - string
    - dict with message/detail/reason/title/code
    - any other value as defensive fallback
    """

    if value is None:
        return _clean_string(fallback) or _default_unavailable_message()

    if isinstance(value, str):
        return _clean_string(value) or _clean_string(fallback) or _default_unavailable_message()

    if isinstance(value, dict):
        for key in ("message", "detail", "reason", "title"):
            text = _clean_string(value.get(key))
            if text:
                return text

        code = _clean_string(value.get("code"))
        if code:
            return code.replace("_", " ").capitalize()

        return _clean_string(fallback) or _default_unavailable_message()

    if isinstance(value, (list, tuple)):
        for item in value:
            text = boundary_unavailable_reason_to_text(
                item,
                fallback=fallback,
            )
            if text:
                return text

        return _clean_string(fallback) or _default_unavailable_message()

    return _clean_string(str(value)) or _clean_string(fallback) or _default_unavailable_message()


def _default_unavailable_message() -> str:
    """
    Resolve the project-level default message safely.

    BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE may be a string or dict depending on
    how constants are defined.
    """

    if isinstance(BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE, str):
        return (
            _clean_string(BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE)
            or "Direct interaction is unavailable."
        )

    if isinstance(BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE, dict):
        for key in ("message", "detail", "reason", "title"):
            text = _clean_string(BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE.get(key))
            if text:
                return text

    return "Direct interaction is unavailable."


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    cleaned = value.strip()
    return cleaned or None


# ---------------------------------------------------------------------
# Boundary item serializer
# ---------------------------------------------------------------------
class UserBoundarySerializer(serializers.ModelSerializer):
    owner = SimpleCustomUserSerializer(read_only=True)
    target = SimpleCustomUserSerializer(read_only=True)

    class Meta:
        model = UserBoundary
        fields = [
            "id",
            "owner",
            "target",
            "boundary_type",
            "source",
            "reason",
            "note",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "target",
            "is_active",
            "created_at",
            "updated_at",
        ]


# ---------------------------------------------------------------------
# Set Boundary / Stillness
# ---------------------------------------------------------------------
class BoundarySetSerializer(serializers.Serializer):
    target_user_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(
            is_deleted=False,
            is_active=True,
        ),
        source="target",
    )
    boundary_type = serializers.ChoiceField(
        choices=BOUNDARY_TYPE_CHOICES,
    )
    source = serializers.CharField(
        required=False,
        allow_blank=True,
        default=BOUNDARY_SOURCE_PROFILE,
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=120,
    )
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
    )

    def validate(self, attrs):
        request = self.context.get("request")
        owner = getattr(request, "user", None)
        target = attrs.get("target")

        if owner and target and owner.id == target.id:
            raise serializers.ValidationError({
                "error": "You cannot create Stillness or Boundary with yourself.",
                "code": "self_boundary_not_allowed",
            })

        return attrs


# ---------------------------------------------------------------------
# Remove Boundary / Stillness
# ---------------------------------------------------------------------
class BoundaryRemoveSerializer(serializers.Serializer):
    target_user_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        source="target",
    )
    boundary_type = serializers.ChoiceField(
        choices=BOUNDARY_TYPE_CHOICES,
    )


# ---------------------------------------------------------------------
# Boundary state serializer
# ---------------------------------------------------------------------
class BoundaryStateSerializer(serializers.Serializer):
    target_user_id = serializers.IntegerField()
    in_stillness = serializers.BooleanField()
    has_boundary = serializers.BooleanField()
    has_boundary_between = serializers.BooleanField()
    direct_interaction_available = serializers.BooleanField()
    direct_interaction_unavailable_reason = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        if rep.get("direct_interaction_available") is True:
            rep["direct_interaction_unavailable_reason"] = None
            return rep

        rep["direct_interaction_unavailable_reason"] = boundary_unavailable_reason_to_text(
            rep.get("direct_interaction_unavailable_reason")
        )

        return rep
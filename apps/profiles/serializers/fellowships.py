# apps/profiles/serializers/fellowships.py

from django.db.models import Q
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.profiles.models.relationships import Fellowship
from apps.profiles.constants.fellowship import (
    FELLOWSHIP_RELATIONSHIP_CHOICES,
    RECIPROCAL_FELLOWSHIP_CHOICES,
    RECIPROCAL_FELLOWSHIP_MAP,
)
from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer

CustomUser = get_user_model()


# FELLOWSHIP Serializer ---------------------------------------------------------------
class FellowshipSerializer(serializers.ModelSerializer):
    from_user = SimpleCustomUserSerializer(read_only=True)
    to_user = SimpleCustomUserSerializer(read_only=True)
    to_user_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(is_deleted=False, is_active=True),
        write_only=True
    )    
    reciprocal_fellowship_type = serializers.CharField(required=False)

    class Meta:
        model = Fellowship
        fields = [
            'id', 'from_user', 'to_user', 'to_user_id', 'fellowship_type', 'reciprocal_fellowship_type', 'status', 'created_at',
        ]
        read_only_fields = ['from_user', 'to_user', 'created_at']

    def validate_to_user_id(self, value):
        if self.context['request'].user == value:
            raise serializers.ValidationError("You cannot send a request to yourself.")
        return value

    def validate_fellowship_type(self, value):
        valid_types = [choice[0] for choice in FELLOWSHIP_RELATIONSHIP_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError("Invalid fellowship type.")
        return value

    def validate_reciprocal_fellowship_type(self, value):
        if value:
            valid_types = [choice[0] for choice in RECIPROCAL_FELLOWSHIP_CHOICES]
            if value not in valid_types:
                raise serializers.ValidationError("Invalid reciprocal fellowship type.")
        return value

    def validate(self, data):
        from_user = self.context['request'].user
        to_user = data.get('to_user_id')
        fellowship_type = data.get('fellowship_type')
        submitted_reciprocal = data.get("reciprocal_fellowship_type")
        reciprocal_fellowship_type = submitted_reciprocal or RECIPROCAL_FELLOWSHIP_MAP.get(fellowship_type)

        # self-checks
        if from_user == to_user:
            raise serializers.ValidationError({"error": "You cannot send a fellowship request to yourself."})

        # ⛔️ deleted guards
        if getattr(from_user, "is_deleted", False):
            raise serializers.ValidationError({"error": "Your account is deactivated. Reactivate to manage fellowships."})
        if getattr(to_user, "is_deleted", False):
            raise serializers.ValidationError({"error": "You cannot send a fellowship request to a deactivated account."})

        # ⛔️ duplicate guards
        base_qs = Fellowship.objects.filter(from_user__is_deleted=False, to_user__is_deleted=False)

        existing_fellowship = base_qs.filter(
            Q(
                from_user=from_user,
                to_user=to_user,
                fellowship_type=fellowship_type,
                status="Accepted",
            )
            |
            Q(
                from_user=to_user,
                to_user=from_user,
                fellowship_type=reciprocal_fellowship_type,
                status="Accepted",
            )
        ).exists()

        if existing_fellowship:
            raise serializers.ValidationError({
                "error": f"You already have this covenant relationship as '{fellowship_type}'."
            })

        existing_reciprocal_fellowship = base_qs.filter(
            Q(
                from_user=from_user,
                to_user=to_user,
                fellowship_type=reciprocal_fellowship_type,
                status="Accepted",
            )
            |
            Q(
                from_user=to_user,
                to_user=from_user,
                fellowship_type=fellowship_type,
                status="Accepted",
            )
        ).exists()

        if existing_reciprocal_fellowship:
            raise serializers.ValidationError({
                "error": f"A reciprocal covenant relationship already exists as '{reciprocal_fellowship_type}'."
            })

        duplicate_fellowship = base_qs.filter(
            from_user=from_user,
            to_user=to_user,
            fellowship_type=fellowship_type,
            status="Pending",
        ).exists()

        if duplicate_fellowship:
            raise serializers.ValidationError({
                "error": f"You have already sent a pending request as '{fellowship_type}'."
            })

        reciprocal_pending_fellowship = base_qs.filter(
            Q(from_user=from_user, to_user=to_user, status="Pending")
            |
            Q(from_user=to_user, to_user=from_user, status="Pending"),
            fellowship_type__in=[fellowship_type, reciprocal_fellowship_type],
        ).exists()

        if reciprocal_pending_fellowship:
            raise serializers.ValidationError({
                "error": "A pending covenant request already exists between you and this user."
            })

        return data

    def create(self, validated_data):
        to_user = validated_data.pop('to_user_id')
        if getattr(to_user, "is_deleted", False):
            raise serializers.ValidationError("Cannot create fellowship with a deactivated account.")

        reciprocal_fellowship_type = validated_data.pop('reciprocal_fellowship_type', None)
        return Fellowship.objects.create(
            to_user=to_user,
            reciprocal_fellowship_type=reciprocal_fellowship_type,
            **validated_data
        )

    def to_representation(self, instance):
        if getattr(instance.from_user, "is_deleted", False) or getattr(instance.to_user, "is_deleted", False):
            return None
        return super().to_representation(instance)



# apps/sanctuary/serializers.py
from __future__ import annotations
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone

from apps.main.models import TermsAndPolicy
from apps.sanctuary.models import (
    SanctuaryRequest,
    SanctuaryReview,
    SanctuaryOutcome,
    SanctuaryReview,
    SanctuaryParticipantProfile, SanctuaryParticipantAudit
)
from apps.main.constants import SANCTUARY_COUNCIL_RULES
from apps.sanctuary.constants.targets import REQUEST_TYPE_CHOICES
from apps.sanctuary.constants.reasons import REASON_MAP
from apps.sanctuary.constants.states import (
    NO_OPINION,
    VIOLATION_CONFIRMED,
    VIOLATION_REJECTED,
)

# Allowed final votes ----------------------------------------------------------------------
_ALLOWED_FINAL_VOTES = {VIOLATION_CONFIRMED, VIOLATION_REJECTED}



# Custom fields -----------------------------------------------------------------------------
class ContentTypeKeyField(serializers.Field):
    """
    Accepts "app_label.model" and returns ContentType instance.
    Example: "posts.post"
    """

    def to_internal_value(self, data):
        if not isinstance(data, str) or "." not in data:
            raise serializers.ValidationError("content_type must be in format 'app_label.model'.")

        app_label, model = data.split(".", 1)
        try:
            return ContentType.objects.get(app_label=app_label, model=model)
        except ContentType.DoesNotExist:
            raise serializers.ValidationError("Invalid content_type.")

    def to_representation(self, value):
        # value can be ContentType instance
        return f"{value.app_label}.{value.model}"

# Sanctuary request serializers -------------------------------------------------------------
class SanctuaryRequestSerializer(serializers.ModelSerializer):
    # Generic target (safe key)
    content_type = ContentTypeKeyField()
    object_id = serializers.IntegerField(min_value=1)

    # Multi-reason list
    reasons = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
    )

    requester = serializers.ReadOnlyField(source="requester.username")
    assigned_admin = serializers.ReadOnlyField(source="assigned_admin.username")

    class Meta:
        model = SanctuaryRequest
        fields = [
            "id",
            "request_type",
            "reasons",
            "description",
            "status",
            "resolution_mode",
            "tradition_protected",
            "tradition_label",
            "report_count_snapshot",
            "requester",
            "assigned_admin",
            "content_type",
            "object_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "resolution_mode",
            "tradition_protected",
            "tradition_label",
            "report_count_snapshot",
            "requester",
            "assigned_admin",
            "created_at",
            "updated_at",
        ]

    def validate_reasons(self, value):
        # Keep unique reasons
        value = [str(x).strip() for x in value if str(x).strip()]
        if not value:
            raise serializers.ValidationError("At least one reason is required.")

        if len(value) > 10:
            raise serializers.ValidationError("Too many reasons.")

        # Unique
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Duplicate reasons are not allowed.")

        request_type = (self.initial_data.get("request_type") or "").strip()
        allowed = REASON_MAP.get(request_type, {})
        invalid = [r for r in value if r not in allowed]
        if invalid:
            raise serializers.ValidationError(f"Invalid reason(s) for {request_type}: {invalid}")

        return value

    def validate(self, attrs):
        request_type = attrs.get("request_type")
        if request_type not in dict(REQUEST_TYPE_CHOICES):
            raise serializers.ValidationError({"request_type": "Invalid request type."})

        ct = attrs.get("content_type")
        obj_id = attrs.get("object_id")

        # Ensure target exists
        try:
            model_cls = ct.model_class()
            if not model_cls.objects.filter(pk=obj_id).exists():
                raise serializers.ValidationError({"object_id": "Target object not found."})
        except Exception:
            raise serializers.ValidationError({"content_type": "Invalid target model."})

        return attrs
    

# Sanctuary review serializers -------------------------------------------------------------
class SanctuaryReviewSerializer(serializers.ModelSerializer):
    """
    Council review serializer:
    - System creates reviews.
    - Reviewer can submit ONE final vote only (no edits after).
    """

    reviewer = serializers.ReadOnlyField(source="reviewer.username")

    class Meta:
        model = SanctuaryReview
        fields = [
            "id",
            "sanctuary_request",
            "reviewer",
            "review_status",
            "comment",
            "is_primary_tradition_match",
            "assigned_at",
            "reviewed_at",
        ]
        read_only_fields = [
            "sanctuary_request",           # ✅ cannot switch target request
            "reviewer",                    # ✅ system set
            "is_primary_tradition_match",  # ✅ system logic
            "assigned_at",
            "reviewed_at",
        ]

    def validate_review_status(self, value):
        if value not in (NO_OPINION, VIOLATION_CONFIRMED, VIOLATION_REJECTED):
            raise serializers.ValidationError("Invalid review_status.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        # This serializer is for update-only (system creates records)
        if self.instance is None:
            raise serializers.ValidationError("Reviews are created by the system.")

        if not user or not getattr(user, "is_authenticated", False):
            raise PermissionDenied("Authentication required.")

        # Only the assigned reviewer can vote (no staff override)
        if self.instance.reviewer_id != user.id:
            raise PermissionDenied("You can only vote on your own review.")

        # Once voted, it is final forever
        if self.instance.review_status != NO_OPINION:
            raise serializers.ValidationError("Vote already submitted and cannot be edited.")

        # Require review_status to submit the vote (no comment-only patch)
        if "review_status" not in attrs:
            raise serializers.ValidationError({"review_status": "This field is required to submit your vote."})

        new_status = attrs.get("review_status")

        # Must be a final vote, not NO_OPINION
        if new_status == NO_OPINION:
            raise serializers.ValidationError({"review_status": "You must choose a final vote (confirm/reject)."})

        if new_status not in _ALLOWED_FINAL_VOTES:
            raise serializers.ValidationError({"review_status": "Invalid final vote."})

        # Optional: sanitize comment
        comment = (attrs.get("comment") or "").strip()
        if comment and len(comment) > 2000:
            raise serializers.ValidationError({"comment": "Comment too long."})
        attrs["comment"] = comment

        return attrs

    def update(self, instance, validated_data):
        """
        When a final vote is submitted, set reviewed_at once.
        """
        new_status = validated_data.get("review_status")

        # Final vote -> stamp reviewed_at
        if new_status in _ALLOWED_FINAL_VOTES and not instance.reviewed_at:
            instance.reviewed_at = timezone.now()

        # Save fields
        instance.review_status = new_status
        instance.comment = validated_data.get("comment", instance.comment)
        instance.save(update_fields=["review_status", "comment", "reviewed_at"])

        return instance

# Sanctuary outcome serializers -------------------------------------------------------------
class SanctuaryOutcomeSerializer(serializers.ModelSerializer):
    content_type = ContentTypeKeyField()
    assigned_admin = serializers.ReadOnlyField(source="assigned_admin.username")

    class Meta:
        model = SanctuaryOutcome
        fields = [
            "id",
            "outcome_status",
            "sanctuary_requests",
            "content_type",
            "object_id",
            "tradition_protection_granted",
            "tradition_protection_note",
            "is_appealed",
            "appeal_message",
            "appeal_deadline",
            "assigned_admin",
            "admin_reviewed",
            "created_at",
            "finalized_at",
        ]
        read_only_fields = fields  # ✅ lock everything here


# Sanctuary compact serializers ------------------------------------------------------------
class SanctuaryRequestCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = SanctuaryRequest
        fields = [
            'id',
            'request_type',
            'status',
            'resolution_mode',
            'tradition_protected',
        ]


# Sanctuary Review Compact Serializer -------------------------------------------------------
class SanctuaryReviewCompactSerializer(serializers.ModelSerializer):
    reviewer = serializers.ReadOnlyField(source='reviewer.username')

    class Meta:
        model = SanctuaryReview
        fields = [
            'id',
            'review_status',
            'reviewer',
        ]


# Sanctuary Participation Status Serializer ------------------------------------------------
class SanctuaryParticipationStatusSerializer(serializers.Serializer):
    """
    Returned to Settings panel.
    """
    eligible = serializers.BooleanField()
    ineligible_reasons = serializers.ListField(child=serializers.CharField(), allow_empty=True)

    # Gates / Flags
    is_verified_identity = serializers.BooleanField()
    is_townlit_verified = serializers.BooleanField()

    # ParticipationProfile flags
    is_sanctuary_participant = serializers.BooleanField()
    is_sanctuary_eligible = serializers.BooleanField()
    eligible_reason = serializers.CharField(allow_null=True, required=False)
    eligible_changed_at = serializers.DateTimeField(allow_null=True, required=False)

    # Policy info (for UI)
    policy_available = serializers.BooleanField()
    policy_id = serializers.IntegerField(allow_null=True, required=False)
    policy_type = serializers.CharField(allow_blank=True)
    policy_title = serializers.CharField(allow_blank=True)
    policy_language = serializers.CharField(allow_blank=True)
    policy_version_number = serializers.CharField(allow_blank=True)
    policy_last_updated = serializers.DateTimeField(allow_null=True)
    requires_acceptance = serializers.BooleanField()

    # Agreement status
    has_agreed = serializers.BooleanField()
    agreed_at = serializers.DateTimeField(allow_null=True)



# Sanctuary opt-in/out serializers --------------------------------------------------------
class SanctuaryOptInSerializer(serializers.Serializer):
    """
    Frontend should show the policy and then send policy_id here.
    """
    policy_id = serializers.IntegerField(min_value=1)

    def validate_policy_id(self, value):
        qs = TermsAndPolicy.objects.filter(
            pk=value,
            policy_type=SANCTUARY_COUNCIL_RULES,
        )
        if hasattr(TermsAndPolicy, "is_active"):
            qs = qs.filter(is_active=True)

        policy = qs.order_by("-last_updated").first()
        if not policy:
            raise serializers.ValidationError("Invalid or inactive Sanctuary policy.")

        # Optional: if you use this flag in your TermsAndPolicy model
        if getattr(policy, "requires_acceptance", True) is False:
            raise serializers.ValidationError(
                "This policy is configured as non-acceptance and cannot be used for opt-in."
            )
        return value



# Sanctuary counter serializers ------------------------------------------------------------
class SanctuaryCounterSerializer(serializers.Serializer):
    request_type = serializers.CharField()
    content_type = serializers.CharField()
    object_id = serializers.IntegerField()

    count = serializers.IntegerField()
    threshold = serializers.IntegerField()

    has_reported = serializers.BooleanField()
    request_id = serializers.IntegerField(allow_null=True)

from rest_framework import serializers
from .models import CollaborationRequest, JobApplication, ReviewLog

# ----------------------------
# CollaborationRequestSerializer
# ----------------------------
class CollaborationRequestSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    last_reviewed_by = serializers.ReadOnlyField(source="last_reviewed_by.username")
    submitted_at = serializers.DateTimeField(read_only=True)
    company_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = CollaborationRequest
        fields = [
            "id", "user", "full_name", "email", "phone_number",
            "country", "city", "collaboration_type", "collaboration_mode",
            "availability", "message", "allow_contact",
            "status", "admin_comment", "admin_note",
            "last_reviewed_by", "submitted_at",
            "company_name",
        ]
        read_only_fields = ["status", "admin_comment", "admin_note"]

    def create(self, validated_data):
        validated_data.pop("company_name", None)

        user = self.context["request"].user
        if user.is_authenticated:
            validated_data["user"] = user

            if not validated_data.get("email") and user.email:
                validated_data["email"] = user.email

            if not validated_data.get("full_name"):
                name_parts = filter(None, [user.name, user.family])
                validated_data["full_name"] = " ".join(name_parts)

        return super().create(validated_data)


# ----------------------------
# JobApplicationSerializer
# ----------------------------
class JobApplicationSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    last_reviewed_by = serializers.ReadOnlyField(source="last_reviewed_by.username")
    submitted_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            "id", "user", "full_name", "email", "resume", "cover_letter", "position",
            "status", "admin_comment", "admin_note",
            "last_reviewed_by", "submitted_at",
        ]
        read_only_fields = ["status", "admin_comment", "admin_note"]

# ----------------------------
# ReviewLogSerializer (Read-only)
# ----------------------------

class ReviewLogSerializer(serializers.ModelSerializer):
    admin_name = serializers.ReadOnlyField(source="admin.username")
    target_repr = serializers.SerializerMethodField()

    class Meta:
        model = ReviewLog
        fields = [
            "id", "admin", "admin_name", "action", "comment",
            "created_at", "content_type", "object_id", "target_repr"
        ]

    def get_target_repr(self, obj):
        return str(obj.target)

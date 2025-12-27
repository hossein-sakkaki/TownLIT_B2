# apps/posts/serializers/comments.py

from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from apps.posts.models.comment import Comment
from apps.accounts.serializers import SimpleCustomUserSerializer 

class SimpleCommentReadSerializer(serializers.ModelSerializer):
    name = SimpleCustomUserSerializer(read_only=True)
    class Meta:
        model = Comment
        fields = ["id", "name", "comment", "published_at", "is_active"]

class RootCommentReadSerializer(serializers.ModelSerializer):
    """
    Lightweight root comment serializer for paginated 'thread_page' endpoint.
    - DOES NOT include 'responses'
    - Includes 'replies_count' for "Show replies (N)" button
    """
    name = SimpleCustomUserSerializer(read_only=True)
    content_type = serializers.SerializerMethodField()
    object_id = serializers.IntegerField(read_only=True)
    replies_count = serializers.IntegerField(read_only=True)  # will be annotated in queryset

    class Meta:
        model = Comment
        fields = [
            "id", "name", "comment", "published_at", "is_active",
            "content_type", "object_id", "recomment", "replies_count",
        ]

    def get_content_type(self, obj):
        ct = getattr(obj, "content_type", None)
        return f"{ct.app_label}.{ct.model}" if ct else None


class CommentReadSerializer(serializers.ModelSerializer):
    """
    Full serializer (used by existing endpoints). Keeps prior behavior,
    still returns 'responses' as list (1-level replies).
    """
    name = SimpleCustomUserSerializer(read_only=True)
    responses = serializers.SerializerMethodField()
    content_type = serializers.SerializerMethodField()
    object_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id", "name", "comment", "published_at", "is_active",
            "content_type", "object_id", "recomment", "responses"
        ]

    def get_content_type(self, obj):
        ct = getattr(obj, "content_type", None)
        return f"{ct.app_label}.{ct.model}" if ct else None

    def get_responses(self, obj):
        qs = obj.responses.all().select_related("name").order_by("published_at")
        if not qs.exists():
            return []
        return SimpleCommentReadSerializer(qs, many=True, context=self.context).data


class CommentWriteSerializer(serializers.ModelSerializer):
    # ✅ make optional for PATCH; still required for create via validate()
    content_type = serializers.CharField(write_only=True, required=False)
    # ✅ do not allow changing these on update (we'll drop them in update())
    object_id = serializers.IntegerField(required=False)
    recomment = serializers.PrimaryKeyRelatedField(
        queryset=Comment.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Comment
        fields = ["id", "comment", "content_type", "object_id", "recomment"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        """
        - create (instance is None): resolve content_type (required).
        - update: if content_type provided, resolve; otherwise keep instance's CT.
        - one-level reply rule: only check when (creating with recomment) or when recomment explicitly provided.
        """
        is_create = self.instance is None

        # resolve content_type
        ct_obj = None
        ct_str = attrs.get("content_type", None)

        if is_create:
            if not ct_str:
                raise serializers.ValidationError({"content_type": "Required."})
        if ct_str:
            try:
                if "." in ct_str:
                    app_label, model = ct_str.split(".", 1)
                    ct_obj = ContentType.objects.get(app_label=app_label, model=model)
                else:
                    ct_obj = ContentType.objects.get(model=ct_str)
            except ContentType.DoesNotExist:
                raise serializers.ValidationError({"content_type": "Invalid content type."})
            attrs["content_type"] = ct_obj
        else:
            # PATCH without content_type → keep instance's content_type (no-op)
            if not is_create:
                attrs.pop("content_type", None)

        # one-level nesting check only when recomment explicitly provided (or on create)
        parent = attrs.get("recomment", None)
        if parent:
            if parent.recomment_id:
                raise serializers.ValidationError(
                    {"recomment": "Reply nesting is limited to one level."}
                )

        return attrs

    def create(self, validated_data):
        # set owner
        user = self.context["request"].user
        validated_data["name"] = user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # ✅ forbid changing identity fields on update
        validated_data.pop("content_type", None)
        validated_data.pop("object_id", None)
        validated_data.pop("recomment", None)
        return super().update(instance, validated_data)

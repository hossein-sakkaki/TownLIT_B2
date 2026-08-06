# apps/posts/serializers/comments.py

from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from apps.posts.models.comment import Comment
from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer 


def _sanctuary_target(obj: Comment) -> dict:
    return {
        "request_type": "content",
        "content_type": "posts.comment",
        "object_id": obj.pk,
        "is_reply": bool(obj.recomment_id),
        "parent_comment_id": obj.recomment_id,
    }
    
    
class SimpleCommentReadSerializer(serializers.ModelSerializer):
    name = SimpleCustomUserSerializer(read_only=True)
    sanctuary_target = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "name",
            "comment",
            "published_at",
            "is_active",
            "sanctuary_target",
        ]

    def get_sanctuary_target(self, obj):
        return _sanctuary_target(obj)

class RootCommentReadSerializer(serializers.ModelSerializer):
    name = SimpleCustomUserSerializer(read_only=True)
    content_type = serializers.SerializerMethodField()
    object_id = serializers.IntegerField(read_only=True)
    replies_count = serializers.IntegerField(read_only=True)
    sanctuary_target = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "name",
            "comment",
            "published_at",
            "is_active",
            "content_type",
            "object_id",
            "recomment",
            "replies_count",
            "sanctuary_target",
        ]

    def get_content_type(self, obj):
        ct = getattr(obj, "content_type", None)
        return f"{ct.app_label}.{ct.model}" if ct else None

    def get_sanctuary_target(self, obj):
        return _sanctuary_target(obj)


class CommentReadSerializer(serializers.ModelSerializer):
    name = SimpleCustomUserSerializer(read_only=True)
    responses = serializers.SerializerMethodField()
    content_type = serializers.SerializerMethodField()
    object_id = serializers.IntegerField(read_only=True)
    sanctuary_target = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "name",
            "comment",
            "published_at",
            "is_active",
            "content_type",
            "object_id",
            "recomment",
            "responses",
            "sanctuary_target",
        ]

    def get_content_type(self, obj):
        ct = getattr(obj, "content_type", None)
        return f"{ct.app_label}.{ct.model}" if ct else None

    def get_sanctuary_target(self, obj):
        return _sanctuary_target(obj)

    def get_responses(self, obj):
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("responses")

        if prefetched is not None:
            replies = [
                reply
                for reply in prefetched
                if reply.is_active
            ]
        else:
            replies = (
                obj.responses
                .filter(is_active=True)
                .select_related("name")
                .order_by("published_at")
            )

        return SimpleCommentReadSerializer(
            replies,
            many=True,
            context=self.context,
        ).data


class CommentWriteSerializer(serializers.ModelSerializer):
    # ✅ make optional for PATCH; still required for create via validate()
    content_type = serializers.CharField(write_only=True, required=False)
    # ✅ do not allow changing these on update (we'll drop them in update())
    object_id = serializers.IntegerField(required=False)
    recomment = serializers.PrimaryKeyRelatedField(
        queryset=Comment.objects.filter(is_active=True),
        required=False,
        allow_null=True,
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
        parent = attrs.get("recomment")

        if parent:
            if not parent.is_active:
                raise serializers.ValidationError({
                    "recomment": "This comment is no longer available."
                })

            if parent.recomment_id:
                raise serializers.ValidationError({
                    "recomment": "Reply nesting is limited to one level."
                })

            if is_create:
                target_content_type = attrs.get("content_type")
                target_object_id = attrs.get("object_id")

                if (
                    target_content_type
                    and parent.content_type_id != target_content_type.id
                ):
                    raise serializers.ValidationError({
                        "recomment": "Reply target does not match the parent comment."
                    })

                if (
                    target_object_id is not None
                    and parent.object_id != target_object_id
                ):
                    raise serializers.ValidationError({
                        "recomment": "Reply target does not match the parent comment."
                    })

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

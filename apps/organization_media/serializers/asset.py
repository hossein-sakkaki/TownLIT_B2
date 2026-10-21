# apps/organization_media/serializers/asset.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-28.
# Last Update by Hossein Sakkaki on 2026-10-19.

import uuid

from rest_framework import serializers

from apps.media_conversion.services.serializer_gate import gate_media_payload
from apps.organization_media.models import OrganizationMediaAsset


class OrganizationMediaAssetSerializer(serializers.ModelSerializer):
    organization_public_id = serializers.UUIDField(source="organization.public_id", read_only=True)
    asset_target = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    is_selectable_intro_video = serializers.SerializerMethodField()
    aspect_ratio = serializers.SerializerMethodField()
    duration_ms = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationMediaAsset
        fields = [
            "id", "public_id", "organization_public_id", "kind", "status",
            "file_url", "thumbnail_url", "asset_target", "alt_text", "caption",
            "aspect_ratio", "duration_ms", "is_selectable_intro_video",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def _viewer(self):
        return getattr(self.context.get("request"), "user", None)

    def get_asset_target(self, obj):
        return {"app_label": obj._meta.app_label, "model": obj._meta.model_name, "object_id": obj.pk}

    def _url(self, obj, field_name):
        if not obj.can_deliver_asset(viewer=self._viewer(), field_name=field_name, intent="view"):
            return None
        value = getattr(obj, field_name, None)
        if not value:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(value.url) if request else value.url

    def get_file_url(self, obj):
        return self._url(obj, "file")

    def get_thumbnail_url(self, obj):
        return self._url(obj, "thumbnail")

    def get_is_selectable_intro_video(self, obj):
        return obj.kind == obj.Kind.VIDEO and obj.is_ready_for_publication()

    def get_aspect_ratio(self, obj):
        return obj.get_media_asset("file").get("aspect_ratio")

    def get_duration_ms(self, obj):
        return obj.get_media_asset("file").get("duration_ms")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data = gate_media_payload(
            obj=instance, data=data, viewer=self._viewer(), field_name="file",
            require_job=True, include_job_target=True,
        )
        if not instance.is_ready_for_publication():
            data["file_url"] = None
            data["thumbnail_url"] = None
        return data


class OrganizationMediaAssetCreateSerializer(serializers.Serializer):
    public_id = serializers.UUIDField(required=False, default=uuid.uuid4)
    update_public_id = serializers.UUIDField(required=False, allow_null=True)
    kind = serializers.ChoiceField(choices=OrganizationMediaAsset.Kind.choices)
    file = serializers.FileField()
    thumbnail = serializers.ImageField(required=False, allow_null=True)
    alt_text = serializers.CharField(required=False, allow_blank=True, max_length=300, default="")
    caption = serializers.CharField(required=False, allow_blank=True, default="")

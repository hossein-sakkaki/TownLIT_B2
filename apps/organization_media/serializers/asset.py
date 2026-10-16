# apps/organization_media/serializers/asset.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-28.
# Last Update by Hossein Sakkaki on 2026-09-28.

from rest_framework import serializers

from apps.organization_media.models import OrganizationMediaAsset


def _file_url(field, request=None):
    if not field:
        return None

    try:
        url = field.url
    except Exception:
        return None

    return request.build_absolute_uri(url) if request else url


class OrganizationMediaAssetSerializer(serializers.ModelSerializer):
    organization_public_id = serializers.UUIDField(
        source="organization.public_id",
        read_only=True,
    )
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    is_selectable_intro_video = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationMediaAsset
        fields = [
            "public_id",
            "organization_public_id",
            "kind",
            "status",
            "file_url",
            "thumbnail_url",
            "alt_text",
            "caption",
            "is_selectable_intro_video",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_file_url(self, obj):
        return _file_url(obj.file, self.context.get("request"))

    def get_thumbnail_url(self, obj):
        return _file_url(obj.thumbnail, self.context.get("request"))

    def get_is_selectable_intro_video(self, obj):
        return (
            obj.kind == OrganizationMediaAsset.Kind.VIDEO
            and obj.status == OrganizationMediaAsset.Status.READY
        )
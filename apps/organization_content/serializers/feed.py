# apps/organization_content/serializers/feed.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-28.
# Last Update by Hossein Sakkaki on 2026-09-28.

from rest_framework import serializers

from apps.organization_content.models import (
    OrganizationFeedEntry,
    OrganizationUpdate,
)
from apps.organization_content.serializers.update import (
    PublicOrganizationUpdateSerializer,
)


class PublicOrganizationFeedEntrySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    update = serializers.SerializerMethodField()
    module_reference = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationFeedEntry
        fields = [
            "id",
            "source",
            "is_pinned",
            "starts_at",
            "expires_at",
            "update",
            "module_reference",
        ]
        read_only_fields = fields

    def get_update(self, obj):
        target = obj.content_object

        if not isinstance(target, OrganizationUpdate):
            return None

        return PublicOrganizationUpdateSerializer(
            target,
            context=self.context,
        ).data

    def get_module_reference(self, obj):
        if obj.source != OrganizationFeedEntry.Source.MODULE:
            return None

        target = obj.content_object

        if not target:
            return None

        from apps.organization_media.models import ChurchTeachingContent

        if isinstance(target, ChurchTeachingContent):
            return {
                "module_key": "church",
                "content_kind": "church_teaching",
                "public_id": str(target.public_id),
            }

        return None
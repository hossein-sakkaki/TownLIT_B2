# apps/core/journey_streams/serializers.py

from __future__ import annotations

from rest_framework import serializers

from apps.accounts.mixins import AvatarURLMixin
from apps.core.journey_streams.constants import JOURNEY_STREAM_KIND
from apps.posts.models.journey import Journey
from apps.posts.serializers.journeys import JourneyStreamEntrySerializer


class JourneyStreamOwnerSerializer(
    AvatarURLMixin,
    serializers.Serializer,
):
    """
    Compact Journey owner.
    """

    def to_representation(self, instance):
        member = instance
        user = getattr(member, "user", None)

        if user is None:
            return None

        label = getattr(user, "label", None)

        full_name = " ".join(
            part
            for part in (
                getattr(user, "name", None),
                getattr(user, "family", None),
            )
            if part
        ).strip()

        return {
            "id": user.pk,
            "username": user.username,
            "name": getattr(user, "name", None),
            "family": getattr(user, "family", None),
            "full_name": full_name or user.username,
            "profile_url": f"/lit/{user.username}",
            "avatar_url": self.build_avatar_url(user),
            "avatar_cdn_url": self.build_avatar_cdn_url(user),
            "avatar_version": getattr(user, "avatar_version", None),
            "label_color": getattr(label, "color", None),
            "is_verified_identity": bool(
                getattr(user, "is_verified_identity", False)
            ),
            "is_townlit_verified": bool(
                getattr(member, "is_townlit_verified", False)
            ),
            "is_private": bool(
                getattr(member, "is_privacy", False)
            ),
        }


class JourneyFriendStreamSerializer(serializers.ModelSerializer):
    """
    Dedicated Journey Stream payload.
    """

    kind = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    relationship = serializers.SerializerMethodField()
    mutual_connector_count = serializers.SerializerMethodField()
    rank_score = serializers.SerializerMethodField()
    entries = serializers.SerializerMethodField()
    active_entries_count = serializers.SerializerMethodField()
    unseen_entries_count = serializers.SerializerMethodField()
    latest_entry_id = serializers.SerializerMethodField()
    latest_thumbnail_target = serializers.SerializerMethodField()
    expires_at = serializers.SerializerMethodField()

    class Meta:
        model = Journey

        fields = (
            "kind",
            "id",
            "slug",
            "local_date",
            "timezone_name",
            "palette_mode",
            "display_seed",
            "relationship",
            "mutual_connector_count",
            "rank_score",
            "owner",
            "active_entries_count",
            "unseen_entries_count",
            "latest_entry_id",
            "latest_thumbnail_target",
            "expires_at",
            "entries",
            "created_at",
            "updated_at",
        )

        read_only_fields = fields

    def _entries(self, obj) -> list:
        return list(
            getattr(obj, "ordered_entries", ()) or ()
        )

    def _latest_entry(self, obj):
        entries = self._entries(obj)

        if not entries:
            return None

        return max(
            entries,
            key=lambda entry: (
                entry.published_at,
                entry.pk,
            ),
        )

    def get_kind(self, obj):
        return JOURNEY_STREAM_KIND

    def get_owner(self, obj):
        owner = getattr(
            obj,
            "_journey_stream_owner",
            None,
        )

        if owner is None:
            return None

        return JourneyStreamOwnerSerializer(
            owner,
            context=self.context,
        ).data

    def get_relationship(self, obj):
        return getattr(
            obj,
            "_journey_stream_relationship",
            None,
        )

    def get_mutual_connector_count(self, obj):
        return int(
            getattr(
                obj,
                "_journey_stream_mutual_count",
                0,
            )
            or 0
        )

    def get_rank_score(self, obj):
        return int(
            getattr(
                obj,
                "_journey_stream_rank_score",
                0,
            )
            or 0
        )

    def get_entries(self, obj):
        return JourneyStreamEntrySerializer(
            self._entries(obj),
            many=True,
            context=self.context,
        ).data

    def get_active_entries_count(self, obj):
        return len(self._entries(obj))

    def get_unseen_entries_count(self, obj):
        if bool(
            getattr(
                obj,
                "_journey_stream_is_owner",
                False,
            )
        ):
            return 0

        seen_entry_ids = set(
            self.context.get(
                "seen_entry_ids",
                (),
            )
        )

        return sum(
            1
            for entry in self._entries(obj)
            if entry.pk not in seen_entry_ids
        )

    def get_latest_entry_id(self, obj):
        latest = self._latest_entry(obj)

        return latest.pk if latest else None

    def get_latest_thumbnail_target(self, obj):
        latest = self._latest_entry(obj)

        if latest is None or not latest.thumbnail:
            return None

        return {
            "app_label": "posts",
            "model": "journeyentry",
            "object_id": latest.pk,
            "field_name": "thumbnail",
            "kind": "thumbnail",
        }

    def get_expires_at(self, obj):
        entries = self._entries(obj)

        if not entries:
            return None

        return max(
            entry.expires_at
            for entry in entries
        )
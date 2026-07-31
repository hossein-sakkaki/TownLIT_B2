# apps/posts/serializers/journeys.py

from __future__ import annotations

from functools import lru_cache

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from apps.audio_catalog.serializers import TrackListSerializer, VariantSerializer
from apps.core.ownership.utils import resolve_owner_from_request
from apps.posts.constants.journeys import (
    JourneyRetentionPolicy,
    JourneyViewSource,
)
from apps.posts.models.journey import Journey, JourneyEntry, JourneyEntryView
from apps.posts.serializers.serializers_owner_min import (
    build_owner_dto_from_content_object,
)
from apps.posts.services.journeys.profile_ring import JourneyProfileRingResult
from apps.posts.services.journeys.publish import publish_journey_entry
from apps.posts.services.journeys.views import record_journey_entry_view


# -------------------------------------------------
# Cached identities
# -------------------------------------------------
@lru_cache(maxsize=1)
def journey_entry_content_type_id() -> int:
    """
    Cache the JourneyEntry ContentType ID per process.
    """

    return ContentType.objects.get_for_model(
        JourneyEntry,
        for_concrete_model=False,
    ).pk


def asset_target(obj, field_name: str, kind: str) -> dict:
    """
    Build a private Asset Delivery target.
    """

    return {
        "app_label": obj._meta.app_label,
        "model": obj._meta.model_name,
        "object_id": obj.pk,
        "field_name": field_name,
        "kind": kind,
    }


def _request_owner_identity(
    context: dict,
) -> tuple[int | None, int | None]:
    """
    Resolve and cache the active owner identity.
    """

    cached = context.get("_journey_request_owner_identity")

    if cached is not None:
        return cached

    request = context.get("request")

    if not request or not request.user.is_authenticated:
        identity = (None, None)
        context["_journey_request_owner_identity"] = identity
        return identity

    owner = resolve_owner_from_request(request)

    if owner is None:
        identity = (None, None)
        context["_journey_request_owner_identity"] = identity
        return identity

    owner_ct = ContentType.objects.get_for_model(
        owner.__class__,
        for_concrete_model=False,
    )

    identity = (owner_ct.pk, owner.pk)
    context["_journey_request_owner_identity"] = identity

    return identity


def _entry_is_request_owner(
    *,
    obj: JourneyEntry,
    context: dict,
) -> bool:
    owner_ct_id, owner_object_id = _request_owner_identity(context)

    return bool(
        owner_ct_id is not None
        and owner_object_id is not None
        and obj.content_type_id == owner_ct_id
        and obj.object_id == owner_object_id
    )


# -------------------------------------------------
# Music serializers
# -------------------------------------------------
class JourneyMusicSerializer(serializers.Serializer):
    """
    Full music payload for Journey detail.
    """

    track = serializers.SerializerMethodField()
    variant = serializers.SerializerMethodField()

    clip_start_ms = serializers.IntegerField(source="music_clip_start_ms")
    clip_end_ms = serializers.IntegerField(source="music_clip_end_ms")

    volume = serializers.DecimalField(
        source="music_volume",
        max_digits=4,
        decimal_places=3,
    )

    attribution_text = serializers.CharField(
        source="music_attribution_text",
    )

    def get_track(self, obj):
        if not obj.music_track_id:
            return None

        return TrackListSerializer(
            obj.music_track,
            context=self.context,
        ).data

    def get_variant(self, obj):
        if not obj.music_variant_id:
            return None

        return VariantSerializer(
            obj.music_variant,
            context=self.context,
        ).data

# -------------------------------------------------
# Stream music serializers
# -------------------------------------------------
class JourneyStreamMusicSerializer(serializers.Serializer):
    """
    Compact music payload for Journey Stream.

    Playback identity and legal attribution remain unchanged.
    Dedicated display fields keep Stream UI independent from
    the full Audio Catalog serializer contract.
    """

    display_title = serializers.SerializerMethodField()
    display_artist = serializers.SerializerMethodField()

    track_id = serializers.IntegerField(
        source="music_track_id",
    )

    track_public_id = serializers.UUIDField(
        source="music_track.public_id",
    )

    variant_id = serializers.IntegerField(
        source="music_variant_id",
    )

    variant_public_id = serializers.UUIDField(
        source="music_variant.public_id",
    )

    clip_start_ms = serializers.IntegerField(
        source="music_clip_start_ms",
    )

    clip_end_ms = serializers.IntegerField(
        source="music_clip_end_ms",
    )

    volume = serializers.DecimalField(
        source="music_volume",
        max_digits=4,
        decimal_places=3,
    )

    attribution_text = serializers.CharField(
        source="music_attribution_text",
        allow_blank=True,
    )

    def get_display_title(self, obj) -> str:
        track = getattr(
            obj,
            "music_track",
            None,
        )

        if track is None:
            return ""

        return (
            getattr(
                track,
                "title",
                "",
            )
            or ""
        ).strip()

    def get_display_artist(self, obj) -> str:
        track = getattr(
            obj,
            "music_track",
            None,
        )

        if track is None:
            return ""

        links = list(
            track.contributor_links.all()
        )

        active_links = [
            link
            for link in links
            if (
                getattr(
                    link,
                    "contributor",
                    None,
                )
                is not None
                and bool(
                    getattr(
                        link.contributor,
                        "is_active",
                        True,
                    )
                )
            )
        ]

        role_priority = (
            "primary_artist",
            "performer",
            "composer",
        )

        for role in role_priority:
            names = self._contributor_names(
                active_links,
                role=role,
            )

            if names:
                return " & ".join(names)

        return ""

    @staticmethod
    def _contributor_names(
        links,
        *,
        role: str,
    ) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()

        for link in links:
            if getattr(link, "role", None) != role:
                continue

            contributor = getattr(
                link,
                "contributor",
                None,
            )

            if contributor is None:
                continue

            name = (
                getattr(
                    contributor,
                    "display_name",
                    "",
                )
                or ""
            ).strip()

            if not name:
                continue

            identity = name.casefold()

            if identity in seen:
                continue

            seen.add(identity)
            names.append(name)

        return names

# -------------------------------------------------
# Shared JourneyEntry base
# -------------------------------------------------
class JourneyEntryBaseSerializer(serializers.ModelSerializer):
    rendered_asset = serializers.SerializerMethodField()
    thumbnail_asset = serializers.SerializerMethodField()
    reaction_target = serializers.SerializerMethodField()

    is_live = serializers.BooleanField(read_only=True)
    is_archived = serializers.BooleanField(read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = JourneyEntry

        fields = (
            "id",
            "slug",
            "sequence",
            "media_type",
            "visual_source_type",
            "rendered_asset",
            "thumbnail_asset",
            "display_duration_ms",
            "visibility",
            "retention_policy",
            "published_at",
            "expires_at",
            "archived_at",
            "is_live",
            "is_archived",
            "reactions_count",
            "reactions_breakdown",
            "reaction_target",
            "is_owner",
        )

        read_only_fields = fields

    def get_rendered_asset(self, obj):
        if not obj.rendered_image:
            return None

        return asset_target(
            obj,
            "rendered_image",
            "image",
        )

    def get_thumbnail_asset(self, obj):
        if not obj.thumbnail:
            return None

        return asset_target(
            obj,
            "thumbnail",
            "thumbnail",
        )

    def get_reaction_target(self, obj):
        return {
            "content_type": "posts.journeyentry",
            "content_type_id": journey_entry_content_type_id(),
            "object_id": obj.pk,
        }

    def get_is_owner(self, obj):
        return _entry_is_request_owner(
            obj=obj,
            context=self.context,
        )


# -------------------------------------------------
# Standalone detail Entry serializer
# -------------------------------------------------
class JourneyEntrySerializer(JourneyEntryBaseSerializer):
    """
    Full standalone JourneyEntry payload.
    """

    owner = serializers.SerializerMethodField()
    music = serializers.SerializerMethodField()

    class Meta(JourneyEntryBaseSerializer.Meta):
        fields = (
            *JourneyEntryBaseSerializer.Meta.fields,
            "music",
            "owner",
        )

        read_only_fields = fields

    def get_music(self, obj):
        if not obj.has_music:
            return None

        return JourneyMusicSerializer(
            obj,
            context=self.context,
        ).data

    def get_owner(self, obj):
        return build_owner_dto_from_content_object(
            obj,
            context=self.context,
        )


# -------------------------------------------------
# Nested Entry serializer
# -------------------------------------------------
class JourneyNestedEntrySerializer(JourneyEntryBaseSerializer):
    """
    Entry nested inside one Journey.

    Owner is omitted because Journey already includes it once.
    """

    music = serializers.SerializerMethodField()

    class Meta(JourneyEntryBaseSerializer.Meta):
        fields = (
            *JourneyEntryBaseSerializer.Meta.fields,
            "music",
        )

        read_only_fields = fields

    def get_music(self, obj):
        if not obj.has_music:
            return None

        return JourneyMusicSerializer(
            obj,
            context=self.context,
        ).data


# -------------------------------------------------
# Full Journey serializer
# -------------------------------------------------
class JourneySerializer(serializers.ModelSerializer):
    """
    Full Journey detail/archive payload.
    """

    entries = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()

    entry_count = serializers.IntegerField(read_only=True)
    remaining_capacity = serializers.IntegerField(read_only=True)
    max_entries = serializers.IntegerField(read_only=True)

    close = serializers.SerializerMethodField()

    class Meta:
        model = Journey

        fields = (
            "id",
            "slug",
            "local_date",
            "timezone_name",
            "palette_mode",
            "display_seed",
            "entry_count",
            "remaining_capacity",
            "max_entries",
            "entries",
            "close",
            "owner",
            "created_at",
            "updated_at",
        )

        read_only_fields = fields

    def get_entries(self, obj):
        entries = getattr(obj, "ordered_entries", None)

        if entries is None:
            entries = obj.entries.filter(
                is_active=True,
            ).order_by(
                "sequence",
                "id",
            )

        return JourneyNestedEntrySerializer(
            entries,
            many=True,
            context=self.context,
        ).data

    def get_owner(self, obj):
        return build_owner_dto_from_content_object(
            obj,
            context=self.context,
        )

    def get_close(self, obj):
        if not obj.closed_at:
            return None

        request = self.context.get("request")

        viewer = (
            request.user
            if request and request.user.is_authenticated
            else None
        )

        owner_user = obj.owner_user

        is_owner = bool(
            viewer
            and owner_user
            and viewer.pk == owner_user.pk
        )

        if obj.close_is_private and not is_owner:
            return None

        return {
            "text": obj.close_text,
            "is_private": obj.close_is_private,
            "closed_at": obj.closed_at,
        }


# -------------------------------------------------
# Ultra-light Profile Ring serializer
# -------------------------------------------------
class JourneyProfileRingSerializer(serializers.Serializer):
    """
    Lightweight Journey state for profile avatars.
    """

    has_active_journey = serializers.BooleanField()

    active_journey_id = serializers.IntegerField(allow_null=True)
    active_journey_slug = serializers.CharField(allow_null=True)

    active_entries_count = serializers.IntegerField()
    unseen_entries_count = serializers.IntegerField()

    latest_entry_id = serializers.IntegerField(allow_null=True)
    latest_thumbnail_target = serializers.JSONField(allow_null=True)

    palette_mode = serializers.CharField(allow_null=True)
    expires_at = serializers.DateTimeField(allow_null=True)

    def to_representation(self, instance):
        if isinstance(instance, JourneyProfileRingResult):
            instance = instance.as_dict()

        return super().to_representation(instance)


# -------------------------------------------------
# Ultra-light Stream Entry serializer
# -------------------------------------------------
class JourneyStreamEntrySerializer(serializers.ModelSerializer):
    """
    Compact entry for Universal Stream.
    """

    rendered_asset = serializers.SerializerMethodField()
    thumbnail_asset = serializers.SerializerMethodField()
    music = serializers.SerializerMethodField()
    reaction_target = serializers.SerializerMethodField()

    class Meta:
        model = JourneyEntry

        fields = (
            "id",
            "slug",
            "sequence",
            "media_type",
            "visual_source_type",
            "rendered_asset",
            "thumbnail_asset",
            "display_duration_ms",
            "music",
            "reactions_count",
            "reactions_breakdown",
            "reaction_target",
            "published_at",
            "expires_at",
        )

        read_only_fields = fields

    def get_rendered_asset(self, obj):
        if not obj.rendered_image:
            return None

        return asset_target(
            obj,
            "rendered_image",
            "image",
        )

    def get_thumbnail_asset(self, obj):
        if not obj.thumbnail:
            return None

        return asset_target(
            obj,
            "thumbnail",
            "thumbnail",
        )

    def get_music(self, obj):
        if not obj.has_music:
            return None

        return JourneyStreamMusicSerializer(
            obj,
            context=self.context,
        ).data

    def get_reaction_target(self, obj):
        return {
            "content_type": "posts.journeyentry",
            "content_type_id": journey_entry_content_type_id(),
            "object_id": obj.pk,
        }


# -------------------------------------------------
# Ultra-light Stream Journey serializer
# -------------------------------------------------
class JourneyStreamPayloadSerializer(serializers.ModelSerializer):
    """
    Journey payload for Universal Stream only.

    Owner is intentionally omitted.
    Universal Stream resolves compact owner once.
    """

    entries = serializers.SerializerMethodField()
    active_entries_count = serializers.SerializerMethodField()
    latest_thumbnail_target = serializers.SerializerMethodField()
    expires_at = serializers.SerializerMethodField()

    class Meta:
        model = Journey

        fields = (
            "id",
            "slug",
            "local_date",
            "palette_mode",
            "display_seed",
            "active_entries_count",
            "latest_thumbnail_target",
            "expires_at",
            "entries",
            "created_at",
            "updated_at",
        )

        read_only_fields = fields

    def _entries(self, obj) -> list:
        entries = getattr(obj, "ordered_entries", None)

        if entries is None:
            entries = list(
                obj.entries.filter(
                    is_active=True,
                    is_hidden=False,
                    archived_at__isnull=True,
                ).order_by(
                    "sequence",
                    "id",
                )
            )

        return entries

    def get_entries(self, obj):
        return JourneyStreamEntrySerializer(
            self._entries(obj),
            many=True,
            context=self.context,
        ).data

    def get_active_entries_count(self, obj):
        return len(self._entries(obj))

    def get_latest_thumbnail_target(self, obj):
        entries = self._entries(obj)

        if not entries:
            return None

        latest = max(
            entries,
            key=lambda item: (
                item.published_at,
                item.sequence,
                item.pk,
            ),
        )

        if not latest.thumbnail:
            return None

        return asset_target(
            latest,
            "thumbnail",
            "thumbnail",
        )

    def get_expires_at(self, obj):
        entries = self._entries(obj)

        if not entries:
            return None

        return max(item.expires_at for item in entries)


# -------------------------------------------------
# Profile Journey map serializer
# -------------------------------------------------
class JourneyProfileMapSerializer(
    serializers.ModelSerializer,
):
    """
    Compact Journey chapter for the profile map.

    One result represents one local day.
    Its entries are rendered as a layered map node.
    """

    entries = serializers.SerializerMethodField()
    entry_count = serializers.SerializerMethodField()
    latest_entry_id = serializers.SerializerMethodField()
    latest_thumbnail_target = (
        serializers.SerializerMethodField()
    )
    expires_at = serializers.SerializerMethodField()
    is_active_today = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = Journey

        fields = (
            "id",
            "slug",
            "local_date",
            "timezone_name",
            "palette_mode",
            "display_seed",
            "entry_count",
            "latest_entry_id",
            "latest_thumbnail_target",
            "expires_at",
            "is_active_today",
            "entries",
            "created_at",
            "updated_at",
        )

        read_only_fields = fields

    def _entries(
        self,
        obj,
    ) -> list[JourneyEntry]:
        return list(
            getattr(
                obj,
                "ordered_entries",
                (),
            )
            or ()
        )

    def _latest_entry(
        self,
        obj,
    ) -> JourneyEntry | None:
        entries = self._entries(
            obj
        )

        if not entries:
            return None

        return max(
            entries,
            key=lambda entry: (
                entry.published_at,
                entry.sequence,
                entry.pk,
            ),
        )

    def get_entries(
        self,
        obj,
    ):
        return JourneyStreamEntrySerializer(
            self._entries(
                obj
            ),
            many=True,
            context=self.context,
        ).data

    def get_entry_count(
        self,
        obj,
    ) -> int:
        return len(
            self._entries(
                obj
            )
        )

    def get_latest_entry_id(
        self,
        obj,
    ) -> int | None:
        latest = self._latest_entry(
            obj
        )

        return (
            latest.pk
            if latest is not None
            else None
        )

    def get_latest_thumbnail_target(
        self,
        obj,
    ) -> dict | None:
        latest = self._latest_entry(
            obj
        )

        if (
            latest is None
            or not latest.thumbnail
        ):
            return None

        return asset_target(
            latest,
            "thumbnail",
            "thumbnail",
        )

    def get_expires_at(
        self,
        obj,
    ):
        entries = self._entries(
            obj
        )

        if not entries:
            return None

        return max(
            entry.expires_at
            for entry in entries
        )

    def get_is_active_today(
        self,
        obj,
    ) -> bool:
        return bool(
            getattr(
                obj,
                "_journey_profile_is_active_today",
                False,
            )
        )
        
        
# -------------------------------------------------
# Write serializers
# -------------------------------------------------
class JourneyPublishSerializer(serializers.Serializer):
    composition_id = serializers.UUIDField()
    render_job_id = serializers.UUIDField()

    composition_revision = serializers.IntegerField(min_value=1)

    visibility = serializers.CharField(max_length=20)

    retention_policy = serializers.ChoiceField(
        choices=JourneyRetentionPolicy.choices,
        default=JourneyRetentionPolicy.KEEP,
    )

    timezone = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
    )

    music_track_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    music_variant_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    music_clip_start_ms = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    music_clip_end_ms = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )

    music_volume = serializers.DecimalField(
        max_digits=4,
        decimal_places=3,
        min_value=0,
        max_value=1,
        default=1,
    )

    def create(self, validated_data):
        request = self.context["request"]
        owner = resolve_owner_from_request(request)

        try:
            return publish_journey_entry(
                user=request.user,
                owner=owner,
                requested_timezone=validated_data.pop(
                    "timezone",
                    None,
                ),
                **validated_data,
            )

        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            )


class JourneyCloseSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2_000)
    is_private = serializers.BooleanField(default=True)


class JourneyViewWriteSerializer(serializers.Serializer):
    progress_ms = serializers.IntegerField(
        min_value=0,
        default=0,
    )

    completed = serializers.BooleanField(default=False)

    source = serializers.ChoiceField(
        choices=JourneyViewSource.choices,
        default=JourneyViewSource.OTHER,
    )

    def create(self, validated_data):
        return record_journey_entry_view(
            entry=self.context["entry"],
            viewer=self.context["request"].user,
            **validated_data,
        )


class JourneyViewerSerializer(serializers.ModelSerializer):
    viewer = serializers.SerializerMethodField()

    class Meta:
        model = JourneyEntryView

        fields = (
            "id",
            "viewer",
            "first_viewed_at",
            "last_viewed_at",
            "view_count",
            "max_progress_ms",
            "completed",
            "source",
        )

        read_only_fields = fields

    def get_viewer(self, obj):
        user = obj.viewer

        full_name = " ".join(
            part
            for part in (
                user.name,
                user.family,
            )
            if part
        ).strip()

        return {
            "id": user.pk,
            "username": user.username,
            "full_name": full_name or user.username,
            "is_verified_identity": user.is_verified_identity,
            "avatar_version": user.avatar_version,
        }
        

class JourneyCreationStatusSerializer(serializers.Serializer):
    can_create = serializers.BooleanField()
    reason = serializers.CharField()

    local_date = serializers.DateField()
    timezone_name = serializers.CharField()

    entry_count = serializers.IntegerField(min_value=0)
    remaining_capacity = serializers.IntegerField(min_value=0)
    max_entries = serializers.IntegerField(min_value=1)

    journey_id = serializers.IntegerField(
        min_value=1,
        allow_null=True,
    )

    journey_slug = serializers.CharField(
        allow_blank=True,
        allow_null=True,
    )
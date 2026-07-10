# apps/core/streams/serializers.py

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
from time import perf_counter
from django.conf import settings

from apps.posts.serializers.moments import MomentStreamPayloadSerializer
from apps.posts.serializers.testimonies import TestimonyStreamPayloadSerializer
from apps.posts.serializers.prayers import PrayerStreamPayloadSerializer

from apps.core.boundaries.services.policy import BoundaryPolicy

from apps.core.streams.constants import (
    STREAM_KIND_MOMENT,
    STREAM_KIND_TESTIMONY,
    STREAM_KIND_PRAY,
)
from apps.core.streams.preview import build_stream_preview
from apps.core.streams.resolvers import resolve_stream_subtype

from apps.subtitles.models import VideoTranscript
from apps.subtitles.serializers import (
    VideoTranscriptMiniSerializer,
    SubtitleTrackMiniSerializer,
    VoiceTrackMiniSerializer,
)
from apps.accounts.mixins import AvatarURLMixin


CustomUser = get_user_model()

SERIALIZER_MAP = {
    STREAM_KIND_MOMENT: MomentStreamPayloadSerializer,
    STREAM_KIND_TESTIMONY: TestimonyStreamPayloadSerializer,
    STREAM_KIND_PRAY: PrayerStreamPayloadSerializer,
}

def _stream_serializer_perf_enabled() -> bool:
    return bool(
        getattr(
            settings,
            "STREAM_PERF_LOGS_ENABLED",
            getattr(settings, "DEBUG", False),
        )
    )


def _stream_serializer_time(name: str, started_at: float, **kwargs) -> None:
    if not _stream_serializer_perf_enabled():
        return

    elapsed_ms = int((perf_counter() - started_at) * 1000)

    suffix = " ".join(
        f"{key}={value}"
        for key, value in kwargs.items()
    )


def _stream_serializer_mark(name: str, **kwargs) -> None:
    if not _stream_serializer_perf_enabled():
        return

    suffix = " ".join(
        f"{key}={value}"
        for key, value in kwargs.items()
    )

class StreamItemSerializer(AvatarURLMixin, serializers.Serializer):
    """
    Universal stream item serializer.

    Important:
    - Query layer already applies Boundary visibility filtering.
    - Serializer exposes owner/boundary metadata for iOS safety.
    - Video payload includes subtitle/voice/quality metadata for player controls.
    """

    kind = serializers.CharField()
    id = serializers.IntegerField()
    published_at = serializers.DateTimeField()
    payload = serializers.SerializerMethodField()

    owner_user_id = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()

    in_stillness = serializers.SerializerMethodField()
    has_boundary = serializers.SerializerMethodField()
    has_boundary_between = serializers.SerializerMethodField()
    direct_interaction_available = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._owner_cache = {}
        self._boundary_cache = {}
        self._transcript_cache = {}
        self._payload_serializer_count = 0
        self._boundary_resolve_count = 0
        self._owner_resolve_count = 0

    def _item_cache_key(self, item_or_obj) -> str:
        obj = getattr(item_or_obj, "obj", item_or_obj)
        model_name = obj.__class__.__name__ if obj is not None else "none"
        object_id = getattr(obj, "id", None)

        return f"{model_name}:{object_id}"

    def _cached_owner_user(self, item_or_obj):
        key = self._item_cache_key(item_or_obj)

        if key in self._owner_cache:
            return self._owner_cache[key]

        start = perf_counter()
        obj = getattr(item_or_obj, "obj", item_or_obj)

        owner = self._resolve_owner_user_uncached(obj)

        self._owner_cache[key] = owner
        self._owner_resolve_count += 1

        _stream_serializer_time(
            "Stream.serializer.owner.resolve",
            start,
            key=key,
            ownerID=getattr(owner, "id", None),
            count=self._owner_resolve_count,
        )

        return owner

    def _cached_boundary_state_for(self, target_user):
        user_id = getattr(target_user, "id", None)

        if not user_id:
            return self._open_boundary_state()

        if user_id in self._boundary_cache:
            return self._boundary_cache[user_id]

        start = perf_counter()

        state = self._boundary_state_for_uncached(target_user)

        self._boundary_cache[user_id] = state
        self._boundary_resolve_count += 1

        _stream_serializer_time(
            "Stream.serializer.boundary.resolve",
            start,
            targetID=user_id,
            count=self._boundary_resolve_count,
        )

        return state
    
    
    # ------------------------------------------------------------------
    # Main payload
    # ------------------------------------------------------------------
    def get_payload(self, item):
        start = perf_counter()

        serializer_cls = SERIALIZER_MAP.get(item.kind)
        if not serializer_cls:
            return None

        serializer_start = perf_counter()

        serializer = serializer_cls(
            item.obj,
            context=self.context,
        )

        raw = serializer.data

        self._payload_serializer_count += 1

        _stream_serializer_time(
            "Stream.serializer.payload.base",
            serializer_start,
            kind=item.kind,
            objectID=getattr(item.obj, "id", None),
            count=self._payload_serializer_count,
        )

        if raw is None:
            return None

        data = dict(raw)

        subtype_start = perf_counter()
        subtype = resolve_stream_subtype(item.obj) or ""

        _stream_serializer_time(
            "Stream.serializer.payload.subtype",
            subtype_start,
            kind=item.kind,
            objectID=getattr(item.obj, "id", None),
            subtype=subtype,
        )

        preview_start = perf_counter()

        data["preview"] = self._safe_preview_for(
            item.obj,
            subtype=subtype,
        )

        _stream_serializer_time(
            "Stream.serializer.payload.preview",
            preview_start,
            kind=item.kind,
            objectID=getattr(item.obj, "id", None),
            subtype=subtype,
        )

        metadata_start = perf_counter()

        data = self._attach_video_playback_metadata(
            data=data,
            obj=item.obj,
            kind=item.kind,
            subtype=subtype,
        )

        if item.kind == STREAM_KIND_PRAY:
            data = self._attach_prayer_response_preview(
                data=data,
                prayer=item.obj,
            )

        _stream_serializer_time(
            "Stream.serializer.payload.metadata",
            metadata_start,
            kind=item.kind,
            objectID=getattr(item.obj, "id", None),
            subtype=subtype,
        )

        owner = self._cached_owner_user(item)
        state = self._cached_boundary_state_for(owner)

        data["owner_user_id"] = getattr(owner, "id", None)
        data["owner_username"] = getattr(owner, "username", None)
        data["owner"] = self._compact_owner_payload(
            owner,
            fallback=data.get("owner"),
        )

        data["in_stillness"] = state["in_stillness"]
        data["has_boundary"] = state["has_boundary"]
        data["has_boundary_between"] = state["has_boundary_between"]
        data["direct_interaction_available"] = state["direct_interaction_available"]

        _stream_serializer_time(
            "Stream.serializer.payload.total",
            start,
            kind=item.kind,
            objectID=getattr(item.obj, "id", None),
            subtype=subtype,
        )

        return data

    # ------------------------------------------------------------------
    # Video playback metadata
    # ------------------------------------------------------------------

    def _attach_video_playback_metadata(self, *, data: dict, obj, kind: str, subtype: str) -> dict:
        """
        Attach transcript/subtitle/voice metadata to video stream payload.

        Web can fetch these later, but iOS needs them in stream payload so
        fullscreen video controls can decide which menus to show.
        """

        if subtype != "video":
            data["transcript"] = None
            data["subtitle_tracks"] = []
            data["voice_tracks"] = []
            data["video_qualities"] = []
            return data

        transcript = self._get_video_transcript(obj)

        if not transcript:
            data["transcript"] = None
            data["subtitle_tracks"] = []
            data["voice_tracks"] = []
            data["video_qualities"] = self._video_qualities_for(obj=obj, kind=kind)
            return data

        subtitle_tracks = (
            transcript.subtitle_tracks
            .all()
            .order_by("target_language", "fmt", "id")
        )

        voice_tracks = (
            transcript.voice_tracks
            .select_related("subtitle_track")
            .all()
            .order_by("target_language", "provider", "id")
        )

        data["transcript"] = VideoTranscriptMiniSerializer(
            transcript,
            context=self.context,
        ).data

        data["subtitle_tracks"] = SubtitleTrackMiniSerializer(
            subtitle_tracks,
            many=True,
            context=self.context,
        ).data

        data["voice_tracks"] = VoiceTrackMiniSerializer(
            voice_tracks,
            many=True,
            context=self.context,
        ).data

        data["video_qualities"] = self._video_qualities_for(
            obj=obj,
            kind=kind,
        )

        return data

    def _get_video_transcript(self, obj):
        """
        Resolve VideoTranscript for any content object using GenericForeignKey.
        Cached per serializer instance to avoid repeated transcript lookups.
        """
        if not obj:
            return None

        try:
            content_type = ContentType.objects.get_for_model(
                obj,
                for_concrete_model=False,
            )

            object_id = getattr(obj, "id", None)

            if not object_id:
                return None

            cache_key = f"{content_type.id}:{object_id}"

            if cache_key in self._transcript_cache:
                return self._transcript_cache[cache_key]

            start = perf_counter()

            transcript = (
                VideoTranscript.objects
                .filter(
                    content_type=content_type,
                    object_id=object_id,
                )
                .first()
            )

            self._transcript_cache[cache_key] = transcript

            _stream_serializer_time(
                "Stream.serializer.transcript.resolve",
                start,
                key=cache_key,
                found=bool(transcript),
            )

            return transcript

        except Exception:
            return None

    def _video_qualities_for(self, *, obj, kind: str) -> list[dict]:
        """
        Return HLS quality metadata.

        Current safe behavior:
        - Keep empty unless backend exposes known variants.
        - iOS hides the quality button when there is only Auto.
        """

        video_asset = (
            getattr(obj, "media_assets", None) or {}
        ).get("video")

        if isinstance(video_asset, dict):
            qualities = video_asset.get("qualities")
            if isinstance(qualities, list) and qualities:
                return self._normalize_quality_payload(qualities)
            
        if kind != STREAM_KIND_TESTIMONY:
            return []

        # If your conversion layer stores HLS variant metadata on the object,
        # expose it here. This defensive block supports several common shapes.
        candidates = [
            getattr(obj, "video_qualities", None),
            getattr(obj, "hls_qualities", None),
            getattr(obj, "qualities", None),
        ]

        for value in candidates:
            normalized = self._normalize_quality_payload(value)
            if normalized:
                return normalized

        return []

    def _normalize_quality_payload(self, value) -> list[dict]:
        """
        Normalize possible quality metadata shapes into iOS-friendly payload.
        """
        if not value:
            return []

        if callable(value):
            try:
                value = value()
            except Exception:
                return []

        if not isinstance(value, list):
            return []

        out = []

        for item in value:
            if not isinstance(item, dict):
                continue

            label = item.get("label")
            height = item.get("height")
            peak = (
                item.get("peak_bit_rate")
                or item.get("peakBitRate")
                or item.get("bitrate")
            )

            if not label and height:
                label = f"{height}p"

            if not peak:
                peak = self._estimated_peak_bitrate(height)

            if not label or not peak:
                continue

            out.append({
                "id": item.get("id") or str(height or int(peak)),
                "label": label,
                "height": height,
                "peak_bit_rate": peak,
            })

        return out

    def _estimated_peak_bitrate(self, height):
        """
        Safe fallback when metadata has height but not bitrate.
        """
        try:
            height = int(height)
        except Exception:
            return None

        if height < 360:
            return 700_000
        if height < 480:
            return 1_200_000
        if height < 720:
            return 2_500_000
        if height < 1080:
            return 5_000_000
        return 8_000_000

    # ------------------------------------------------------------------
    # Top-level metadata
    # ------------------------------------------------------------------
    def get_owner_user_id(self, item):
        owner = self._cached_owner_user(item)
        return getattr(owner, "id", None)


    def get_owner_username(self, item):
        owner = self._cached_owner_user(item)
        return getattr(owner, "username", None)


    def get_in_stillness(self, item):
        owner = self._cached_owner_user(item)
        return self._cached_boundary_state_for(owner)["in_stillness"]


    def get_has_boundary(self, item):
        owner = self._cached_owner_user(item)
        return self._cached_boundary_state_for(owner)["has_boundary"]


    def get_has_boundary_between(self, item):
        owner = self._cached_owner_user(item)
        return self._cached_boundary_state_for(owner)["has_boundary_between"]


    def get_direct_interaction_available(self, item):
        owner = self._cached_owner_user(item)
        return self._cached_boundary_state_for(owner)["direct_interaction_available"]

    # ------------------------------------------------------------------
    # Preview helpers
    # ------------------------------------------------------------------

    def _safe_preview_for(self, obj, *, subtype: str) -> dict:
        """
        Build preview safely.
        """

        try:
            return build_stream_preview(
                obj,
                subtype=subtype,
            )
        except Exception:
            return {
                "thumbnail_url": None,
                "image_url": None,
                "poster_url": None,
                "type": getattr(obj, "type", None) if hasattr(obj, "type") else None,
                "has_video": bool(getattr(obj, "video", None)) if hasattr(obj, "video") else False,
            }

    def _attach_prayer_response_preview(self, *, data: dict, prayer) -> dict:
        """
        Add response metadata and preview for prayer.
        """

        response = getattr(prayer, "response", None)

        if not response:
            data["response"] = None
            return data

        response_subtype = "video" if getattr(response, "video", None) else "image"

        existing_response_data = data.get("response")
        response_data = dict(existing_response_data) if isinstance(existing_response_data, dict) else {}

        response_data["id"] = getattr(response, "id", None)
        response_data["result_status"] = getattr(response, "result_status", None)
        response_data["response_text"] = getattr(response, "response_text", None)
        response_data["preview"] = self._safe_preview_for(
            response,
            subtype=response_subtype,
        )

        data["response"] = response_data
        return data

    # ------------------------------------------------------------------
    # Owner resolver
    # ------------------------------------------------------------------

    def _resolve_owner_user_uncached(self, obj):
        """
        Resolve the CustomUser owner behind Moment/Testimony/Prayer.
        """

        if not obj:
            return None

        direct_candidates = [
            "owner",
            "author",
            "user",
            "created_by",
            "uploaded_by",
            "name",
        ]

        for attr in direct_candidates:
            user = self._as_custom_user(getattr(obj, attr, None))
            if user:
                return user

        content_object = getattr(obj, "content_object", None)
        user = self._owner_user_from_profile_like_object(content_object)
        if user:
            return user

        return None

    def _owner_user_from_profile_like_object(self, value):
        """
        Extract CustomUser from profile-like owner objects.
        """

        user = self._as_custom_user(value)
        if user:
            return user

        if not value:
            return None

        profile_user_attrs = [
            "name",
            "user",
            "account",
            "custom_user",
            "owner",
        ]

        for attr in profile_user_attrs:
            user = self._as_custom_user(getattr(value, attr, None))
            if user:
                return user

        return None

    def _as_custom_user(self, value):
        if not value:
            return None

        if getattr(value, "is_anonymous", False):
            return None

        if isinstance(value, CustomUser):
            return value

        return None

    def _compact_owner_payload(self, owner, *, fallback=None):
        """
        Build compact owner payload for stream headers.

        Performance goal:
        - Do NOT use full/public user serializers here.
        - Only expose the few fields iOS stream needs for avatar/header:
        label color, verification, avatar URLs/version, profile URL, names.
        """

        base = dict(fallback) if isinstance(fallback, dict) else {}

        if not owner:
            return base or None

        def first_value(*values):
            for value in values:
                if value is None:
                    continue

                cleaned = str(value).strip()
                if cleaned:
                    return cleaned

            return None

        def first_bool(*values):
            for value in values:
                if value is None:
                    continue

                return bool(value)

            return None

        def first_int(*values):
            for value in values:
                if value is None:
                    continue

                try:
                    return int(value)
                except Exception:
                    continue

            return None

        # -------------------------------------------------
        # Label / border color
        # -------------------------------------------------
        label = getattr(owner, "label", None)

        label_color = first_value(
            base.get("label_color"),
            base.get("labelColor"),
            getattr(label, "color", None),
        )

        # -------------------------------------------------
        # Avatar URLs
        # -------------------------------------------------
        avatar_url = first_value(
            base.get("avatar_url"),
            base.get("avatarURL"),
            self.build_avatar_url(owner),
        )

        avatar_cdn_url = first_value(
            base.get("avatar_cdn_url"),
            base.get("avatarCDNURL"),
            self.build_avatar_cdn_url(owner),
        )

        avatar_version = first_int(
            base.get("avatar_version"),
            base.get("avatarVersion"),
            getattr(owner, "avatar_version", None),
        )

        # -------------------------------------------------
        # Verification
        # -------------------------------------------------
        is_verified_identity = first_bool(
            base.get("is_verified_identity"),
            base.get("isVerifiedIdentity"),
            getattr(owner, "is_verified_identity", None),
        )

        is_townlit_verified = first_bool(
            base.get("is_townlit_verified"),
            base.get("isTownlitVerified"),
            self._owner_is_townlit_verified(owner),
        )

        # -------------------------------------------------
        # Profile URL
        # -------------------------------------------------
        profile_url = first_value(
            base.get("profile_url"),
            base.get("profileURL"),
            self._owner_profile_url(owner),
        )

        # -------------------------------------------------
        # Identity / display
        # -------------------------------------------------
        base["id"] = base.get("id") or getattr(owner, "id", None)

        base["username"] = first_value(
            base.get("username"),
            getattr(owner, "username", None),
        )

        base["name"] = first_value(
            base.get("name"),
            getattr(owner, "name", None),
            getattr(owner, "first_name", None),
        )

        base["family"] = first_value(
            base.get("family"),
            getattr(owner, "family", None),
            getattr(owner, "last_name", None),
        )

        full_name = first_value(
            base.get("full_name"),
            base.get("fullName"),
            " ".join(
                part for part in [
                    base.get("name"),
                    base.get("family"),
                ]
                if part
            ),
        )

        if full_name:
            base["full_name"] = full_name

        if profile_url:
            base["profile_url"] = profile_url

        if avatar_url:
            base["avatar_url"] = avatar_url

        if avatar_cdn_url:
            base["avatar_cdn_url"] = avatar_cdn_url

        if avatar_version is not None:
            base["avatar_version"] = avatar_version

        if label_color:
            base["label_color"] = label_color

            existing_label = base.get("label")
            label_payload = dict(existing_label) if isinstance(existing_label, dict) else {}

            label_payload["color"] = first_value(
                label_payload.get("color"),
                label_color,
            )

            label_name = first_value(
                label_payload.get("name"),
                getattr(label, "name", None),
                getattr(label, "title", None),
            )

            if label_name:
                label_payload["name"] = label_name

            base["label"] = label_payload

        if is_verified_identity is not None:
            base["is_verified_identity"] = bool(is_verified_identity)

        if is_townlit_verified is not None:
            base["is_townlit_verified"] = bool(is_townlit_verified)

        return base

    def _owner_is_townlit_verified(self, owner) -> bool:
        """
        Lightweight TownLIT verification resolver.

        Avoids full user serializers while matching CustomUser serializers:
        True if user has member_profile and member_profile.is_townlit_verified.
        """

        if not owner:
            return False

        try:
            member_profile = getattr(owner, "member_profile", None)
            return bool(
                member_profile
                and getattr(member_profile, "is_townlit_verified", False)
            )
        except Exception:
            return False


    def _owner_profile_url(self, owner) -> str | None:
        if not owner:
            return None

        try:
            if hasattr(owner, "get_absolute_url"):
                return owner.get_absolute_url()
        except Exception:
            return None

        username = getattr(owner, "username", None)

        if username:
            return f"/lit/{username}"

        return None

    # ------------------------------------------------------------------
    # Boundary state
    # ------------------------------------------------------------------

    def _boundary_state_for_uncached(self, target_user):
        """
        Return viewer -> target boundary state.
        """

        request = self.context.get("request")
        viewer = getattr(request, "user", None)

        if not target_user:
            return self._open_boundary_state()

        if not viewer or not getattr(viewer, "is_authenticated", False):
            return self._open_boundary_state()

        if getattr(viewer, "id", None) == getattr(target_user, "id", None):
            return self._open_boundary_state()

        try:
            in_stillness = BoundaryPolicy.is_in_stillness(
                owner=viewer,
                target=target_user,
            )

            has_boundary = BoundaryPolicy.has_boundary(
                owner=viewer,
                target=target_user,
            )

            has_boundary_between = BoundaryPolicy.has_boundary_between(
                viewer,
                target_user,
            )

            return {
                "in_stillness": bool(in_stillness),
                "has_boundary": bool(has_boundary),
                "has_boundary_between": bool(has_boundary_between),
                "direct_interaction_available": not bool(has_boundary_between),
            }

        except Exception:
            return self._open_boundary_state()

    def _open_boundary_state(self):
        return {
            "in_stillness": False,
            "has_boundary": False,
            "has_boundary_between": False,
            "direct_interaction_available": True,
        }
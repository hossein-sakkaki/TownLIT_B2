# apps/core/streams/serializers.py

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.posts.serializers.moments import MomentSerializer
from apps.posts.serializers.testimonies import TestimonySerializer
from apps.posts.serializers.prayers import PrayerSerializer

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


CustomUser = get_user_model()


SERIALIZER_MAP = {
    STREAM_KIND_MOMENT: MomentSerializer,
    STREAM_KIND_TESTIMONY: TestimonySerializer,
    STREAM_KIND_PRAY: PrayerSerializer,
}


class StreamItemSerializer(serializers.Serializer):
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

    # ------------------------------------------------------------------
    # Main payload
    # ------------------------------------------------------------------

    def get_payload(self, item):
        serializer_cls = SERIALIZER_MAP.get(item.kind)
        if not serializer_cls:
            return None

        serializer = serializer_cls(
            item.obj,
            context=self.context,
        )

        raw = serializer.data
        if raw is None:
            return None

        data = dict(raw)

        subtype = resolve_stream_subtype(item.obj) or ""

        data["preview"] = self._safe_preview_for(
            item.obj,
            subtype=subtype,
        )

        # Attach video subtitle / voice / quality metadata for iOS player.
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

        owner = self._resolve_owner_user(item.obj)
        state = self._boundary_state_for(owner)

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
        """
        if not obj:
            return None

        try:
            content_type = ContentType.objects.get_for_model(
                obj,
                for_concrete_model=False,
            )

            return (
                VideoTranscript.objects
                .filter(
                    content_type=content_type,
                    object_id=getattr(obj, "id", None),
                )
                .first()
            )
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
        owner = self._resolve_owner_user(item.obj)
        return getattr(owner, "id", None)

    def get_owner_username(self, item):
        owner = self._resolve_owner_user(item.obj)
        return getattr(owner, "username", None)

    def get_in_stillness(self, item):
        owner = self._resolve_owner_user(item.obj)
        return self._boundary_state_for(owner)["in_stillness"]

    def get_has_boundary(self, item):
        owner = self._resolve_owner_user(item.obj)
        return self._boundary_state_for(owner)["has_boundary"]

    def get_has_boundary_between(self, item):
        owner = self._resolve_owner_user(item.obj)
        return self._boundary_state_for(owner)["has_boundary_between"]

    def get_direct_interaction_available(self, item):
        owner = self._resolve_owner_user(item.obj)
        return self._boundary_state_for(owner)["direct_interaction_available"]

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

    def _resolve_owner_user(self, obj):
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

        Existing serializer owner data wins, but missing fields are filled
        from the resolved CustomUser.
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

        avatar_cdn_url = first_value(
            base.get("avatar_cdn_url"),
            base.get("avatarCDNURL"),
            getattr(owner, "avatar_cdn_url", None),
        )

        avatar_url = first_value(
            base.get("avatar_url"),
            base.get("avatarURL"),
            getattr(owner, "avatar_url", None),
            getattr(owner, "avatar", None),
        )

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

        if avatar_cdn_url:
            base["avatar_cdn_url"] = avatar_cdn_url

        if avatar_url:
            base["avatar_url"] = avatar_url

        # Keep verification/label fields if they exist.
        if "label_color" not in base and hasattr(owner, "label_color"):
            base["label_color"] = getattr(owner, "label_color", None)

        if "is_verified_identity" not in base and hasattr(owner, "is_verified_identity"):
            base["is_verified_identity"] = bool(
                getattr(owner, "is_verified_identity", False)
            )

        if "is_townlit_verified" not in base and hasattr(owner, "is_townlit_verified"):
            base["is_townlit_verified"] = bool(
                getattr(owner, "is_townlit_verified", False)
            )

        return base
    
    # ------------------------------------------------------------------
    # Boundary state
    # ------------------------------------------------------------------

    def _boundary_state_for(self, target_user):
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
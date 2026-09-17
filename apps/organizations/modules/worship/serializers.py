# apps/organizations/modules/worship/serializers.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-07.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from rest_framework import serializers

from apps.audio_catalog.models import (
    AudioCatalog,
    AudioContributor,
    MusicArtwork,
    MusicTrackVariant,
)
from apps.organizations.modules.worship.models import (
    OrganizationMusicContribution,
    OrganizationMusicLicense,
    OrganizationMusicLicenseEvidence,
    OrganizationRightsParty,
)


class WorshipRightsPartySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    rights_party_id = serializers.UUIDField(
        source="rights_party.public_id"
    )
    display_name = serializers.CharField(
        source="rights_party.display_name"
    )
    kind = serializers.CharField(
        source="rights_party.kind"
    )

    class Meta:
        model = OrganizationRightsParty
        fields = (
            "id",
            "rights_party_id",
            "display_name",
            "kind",
            "relationship",
            "is_active",
            "created_at",
        )


class WorshipLicenseSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    licensor = WorshipRightsPartySerializer(read_only=True)
    master_owner = WorshipRightsPartySerializer(read_only=True)
    composition_owner = WorshipRightsPartySerializer(read_only=True)

    class Meta:
        model = OrganizationMusicLicense
        fields = (
            "id",
            "title",
            "reference",
            "status",
            "license_type",
            "license_version",
            "effective_from",
            "effective_until",
            "territory_mode",
            "territory_codes",
            "commercial_use_allowed",
            "ugc_use_allowed",
            "streaming_allowed",
            "synchronization_allowed",
            "adaptation_allowed",
            "clipping_allowed",
            "hosting_allowed",
            "sublicensing_to_end_users_allowed",
            "standalone_download_allowed",
            "external_export_allowed",
            "perpetual_existing_content_allowed",
            "attribution_required",
            "attribution_text",
            "activated_at",
            "revoked_at",
            "revoke_reason",
            "licensor",
            "master_owner",
            "composition_owner",
            "created_at",
            "updated_at",
        )


class WorshipEvidenceSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")

    class Meta:
        model = OrganizationMusicLicenseEvidence
        fields = (
            "id",
            "evidence_type",
            "title",
            "sha256",
            "captured_at",
            "created_at",
        )


class WorshipArtworkSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")

    class Meta:
        model = MusicArtwork
        fields = (
            "id",
            "role",
            "label",
            "is_primary",
            "is_active",
            "is_converted",
            "width",
            "height",
            "sort_order",
        )


class WorshipVariantSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")

    class Meta:
        model = MusicTrackVariant
        fields = (
            "id",
            "variant_type",
            "label",
            "locale",
            "is_default",
            "is_active",
            "is_converted",
            "is_streamable",
            "duration_ms",
            "mime_type",
            "codec",
            "container",
            "bitrate_kbps",
            "sample_rate_hz",
            "channels",
            "sort_order",
        )


class WorshipContributionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    track_id = serializers.UUIDField(source="track.public_id")
    license_id = serializers.UUIDField(source="license.public_id")
    primary_artist_id = serializers.UUIDField(
        source="primary_artist.public_id"
    )
    title = serializers.CharField(source="track.title")
    subtitle = serializers.CharField(source="track.subtitle")
    primary_artist = serializers.CharField(
        source="primary_artist.display_name"
    )
    artworks = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationMusicContribution
        fields = (
            "id",
            "track_id",
            "license_id",
            "primary_artist_id",
            "title",
            "subtitle",
            "primary_artist",
            "credit_text",
            "status",
            "published_at",
            "revoked_at",
            "revoke_reason",
            "artworks",
            "variants",
            "created_at",
            "updated_at",
        )

    def get_artworks(self, obj):
        return WorshipArtworkSerializer(
            obj.track.artworks.all(),
            many=True,
        ).data

    def get_variants(self, obj):
        return WorshipVariantSerializer(
            obj.track.variants.all(),
            many=True,
        ).data


class WorshipRightsPartyCreateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=180)
    kind = serializers.CharField(
        max_length=24,
        default="organization",
    )
    legal_name = serializers.CharField(
        max_length=220,
        required=False,
        allow_blank=True,
    )
    country_code = serializers.CharField(
        max_length=2,
        required=False,
        allow_blank=True,
    )
    website_url = serializers.URLField(
        required=False,
        allow_blank=True,
    )
    contact_email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )
    external_reference = serializers.CharField(
        max_length=220,
        required=False,
        allow_blank=True,
    )
    relationship = serializers.CharField(
        max_length=24,
        default="other",
    )


class WorshipLicenseCreateSerializer(serializers.Serializer):
    licensor_id = serializers.UUIDField()
    master_owner_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    composition_owner_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    title = serializers.CharField(max_length=180)
    reference = serializers.CharField(
        max_length=220,
        required=False,
        allow_blank=True,
    )
    license_type = serializers.CharField(
        max_length=24,
        default="non_exclusive",
    )
    license_version = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    effective_from = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )
    effective_until = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )

    commercial_use_allowed = serializers.BooleanField(default=False)
    ugc_use_allowed = serializers.BooleanField(default=True)
    streaming_allowed = serializers.BooleanField(default=True)
    synchronization_allowed = serializers.BooleanField(default=True)
    adaptation_allowed = serializers.BooleanField(default=False)
    clipping_allowed = serializers.BooleanField(default=True)
    hosting_allowed = serializers.BooleanField(default=True)
    sublicensing_to_end_users_allowed = serializers.BooleanField(default=True)
    perpetual_existing_content_allowed = serializers.BooleanField(default=True)

    attribution_required = serializers.BooleanField(default=False)
    attribution_text = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )


class WorshipEvidenceCreateSerializer(serializers.Serializer):
    evidence_type = serializers.CharField(max_length=32)
    title = serializers.CharField(max_length=180)
    evidence_file = serializers.FileField()
    captured_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )


class WorshipContributionCreateSerializer(serializers.Serializer):
    license_id = serializers.UUIDField()
    catalog_id = serializers.UUIDField()
    primary_artist_id = serializers.UUIDField()

    title = serializers.CharField(max_length=180)
    subtitle = serializers.CharField(
        max_length=180,
        required=False,
        allow_blank=True,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    duration_ms = serializers.IntegerField(min_value=1)
    language_code = serializers.CharField(
        max_length=16,
        required=False,
        allow_blank=True,
    )
    is_instrumental = serializers.BooleanField(default=True)
    has_vocals = serializers.BooleanField(default=False)
    credit_text = serializers.CharField(
        max_length=240,
        required=False,
        allow_blank=True,
    )


class WorshipArtworkUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()
    role = serializers.CharField(
        max_length=20,
        default="primary",
    )
    label = serializers.CharField(
        max_length=120,
        required=False,
        allow_blank=True,
    )
    is_primary = serializers.BooleanField(default=True)


class WorshipAudioUploadSerializer(serializers.Serializer):
    audio_file = serializers.FileField()
    variant_type = serializers.CharField(
        max_length=24,
        default="playback",
    )
    label = serializers.CharField(
        max_length=120,
        required=False,
        allow_blank=True,
    )
    locale = serializers.CharField(
        max_length=16,
        required=False,
        allow_blank=True,
    )
    is_default = serializers.BooleanField(default=True)


class WorshipRevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=240,
        required=False,
        allow_blank=True,
        default="",
    )


class WorshipCatalogChoiceSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")

    class Meta:
        model = AudioCatalog
        fields = (
            "id",
            "name",
            "slug",
        )


class WorshipContributorChoiceSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")

    class Meta:
        model = AudioContributor
        fields = (
            "id",
            "display_name",
            "kind",
        )
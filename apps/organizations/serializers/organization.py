# apps/organizations/serializers/organization.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-09-27.
#

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from rest_framework import serializers

from apps.accounts.models.social import (
    SocialMediaLink,
)
from apps.organization_media.models import (
    OrganizationMediaAsset,
)
from apps.organizations.constants import (
    OrganizationKind,
    OrganizationMembershipStatus,
    OrganizationRepresentativeStatus,
)
from apps.organizations.models import Organization
from apps.organizations.serializers.profile import (
    OrganizationBusinessHourSerializer,
    OrganizationContactPointSerializer,
    OrganizationRepresentativeSerializer,
    OrganizationSocialLinkSerializer,
)


def _organization_file_url(
    field,
    *,
    request=None,
) -> str | None:
    if not field:
        return None

    try:
        url = field.url
    except Exception:
        return None

    return (
        request.build_absolute_uri(
            url
        )
        if request
        else url
    )


def _organization_logo_url(
    obj,
    *,
    request=None,
) -> str | None:
    return _organization_file_url(
        obj.logo,
        request=request,
    )


class OrganizationListSerializer(
    serializers.ModelSerializer
):
    follower_count = serializers.IntegerField(
        read_only=True,
        default=0,
    )

    member_count = serializers.IntegerField(
        read_only=True,
        default=0,
    )

    viewer_relationship = (
        serializers.SerializerMethodField()
    )

    logo_url = (
        serializers.SerializerMethodField()
    )

    thumbnail_url = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = Organization

        fields = [
            "id",
            "public_id",
            "name",
            "short_name",
            "tagline",
            "slug",
            "kind",
            "country",
            "city",
            "logo_url",
            "thumbnail_url",
            "brand_color",
            "service_delivery_mode",
            "follower_count",
            "member_count",
            "viewer_relationship",
        ]

        read_only_fields = fields

    def get_viewer_relationship(
        self,
        obj,
    ):
        request = self.context.get(
            "request"
        )

        user = getattr(
            request,
            "user",
            None,
        )

        if (
            not user
            or not getattr(
                user,
                "is_authenticated",
                False,
            )
        ):
            return None

        connection = (
            obj.connections
            .filter(
                user=user,
                status="active",
            )
            .only(
                "relationship_type"
            )
            .first()
        )

        return (
            connection.relationship_type
            if connection
            else None
        )

    def get_logo_url(
        self,
        obj,
    ):
        return _organization_logo_url(
            obj,
            request=self.context.get(
                "request"
            ),
        )

    def get_thumbnail_url(
        self,
        obj,
    ):
        return _organization_file_url(
            obj.thumbnail,
            request=self.context.get(
                "request"
            ),
        )


class OrganizationSerializer(
    OrganizationListSerializer
):
    cover_image_url = (
        serializers.SerializerMethodField()
    )

    intro_video = (
        serializers.SerializerMethodField()
    )

    contacts = (
        serializers.SerializerMethodField()
    )

    business_hours = (
        serializers.SerializerMethodField()
    )

    representatives = (
        serializers.SerializerMethodField()
    )

    social_links = (
        serializers.SerializerMethodField()
    )

    share_url = (
        serializers.SerializerMethodField()
    )

    qr_payload = (
        serializers.SerializerMethodField()
    )

    share_preview = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = Organization

        fields = [
            # Identity
            "id",
            "public_id",
            "name",
            "short_name",
            "tagline",
            "slug",
            "kind",
            "founded_year",
            "activity_areas",

            # About
            "description",
            "history",
            "statement_of_faith",
            "statement_of_purpose",

            # Visual identity
            "logo_url",
            "cover_image_url",
            "thumbnail_url",
            "brand_color",
            "intro_video",

            # Contact
            "public_email",
            "public_phone_number",
            "website_url",
            "contacts",
            "social_links",

            # Location
            "country",
            "province_region",
            "city",
            "postal_code",
            "address_line1",
            "address_line2",
            "latitude",
            "longitude",
            "location_url",

            # Service / visiting
            "service_delivery_mode",
            "business_hours",
            "visit_instructions",
            "appointment_url",
            "contact_form_url",

            # People
            "representatives",

            # Language
            "primary_language",
            "secondary_language",
            "timezone",

            # Sharing
            "share_url",
            "qr_payload",
            "share_preview",

            # Lifecycle / relationship
            "status",
            "visibility",
            "follower_count",
            "member_count",
            "viewer_relationship",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields

    # ------------------------------------------------------------------
    # Visual identity
    # ------------------------------------------------------------------

    def get_cover_image_url(
        self,
        obj,
    ):
        return _organization_file_url(
            obj.cover_image,
            request=self.context.get(
                "request"
            ),
        )

    def get_intro_video(
        self,
        obj,
    ):
        asset = obj.intro_video

        if not asset:
            return None

        request = self.context.get(
            "request"
        )

        file_field = getattr(
            asset,
            "file",
            None,
        )

        thumbnail_field = getattr(
            asset,
            "thumbnail",
            None,
        )

        return {
            "public_id": str(
                asset.public_id
            ),
            "kind": getattr(
                asset,
                "kind",
                None,
            ),
            "status": getattr(
                asset,
                "status",
                None,
            ),
            "file_url": (
                _organization_file_url(
                    file_field,
                    request=request,
                )
            ),
            "thumbnail_url": (
                _organization_file_url(
                    thumbnail_field,
                    request=request,
                )
            ),
            "alt_text": getattr(
                asset,
                "alt_text",
                "",
            ),
            "caption": getattr(
                asset,
                "caption",
                "",
            ),
        }

    # ------------------------------------------------------------------
    # Contact
    # ------------------------------------------------------------------

    def get_contacts(
        self,
        obj,
    ):
        queryset = (
            obj.contact_points
            .filter(
                is_public=True
            )
            .order_by(
                "-is_primary",
                "sort_order",
                "id",
            )
        )

        return (
            OrganizationContactPointSerializer(
                queryset,
                many=True,
            ).data
        )

    def get_social_links(
        self,
        obj,
    ):
        content_type = (
            ContentType.objects
            .get_for_model(
                Organization,
                for_concrete_model=False,
            )
        )

        queryset = (
            SocialMediaLink.objects
            .select_related(
                "social_media_type"
            )
            .filter(
                content_type=content_type,
                object_id=obj.pk,
                is_active=True,
                social_media_type__is_active=True,
            )
            .order_by(
                "social_media_type__name",
                "id",
            )
        )

        return (
            OrganizationSocialLinkSerializer(
                queryset,
                many=True,
            ).data
        )

    # ------------------------------------------------------------------
    # Business hours
    # ------------------------------------------------------------------

    def get_business_hours(
        self,
        obj,
    ):
        queryset = (
            obj.business_hours
            .all()
            .order_by(
                "weekday",
                "sort_order",
                "id",
            )
        )

        return (
            OrganizationBusinessHourSerializer(
                queryset,
                many=True,
            ).data
        )

    # ------------------------------------------------------------------
    # Public representatives
    # ------------------------------------------------------------------

    def get_representatives(
        self,
        obj,
    ):
        queryset = (
            obj.public_representatives
            .select_related(
                "membership__member__user"
            )
            .filter(
                status=(
                    OrganizationRepresentativeStatus
                    .ACCEPTED
                ),
                membership__status=(
                    OrganizationMembershipStatus
                    .ACTIVE
                ),
                membership__member__is_active=True,
                membership__member__user__is_active=True,
            )
            .order_by(
                "-is_primary",
                "sort_order",
                "id",
            )
        )

        return (
            OrganizationRepresentativeSerializer(
                queryset,
                many=True,
                context=self.context,
            ).data
        )

    # ------------------------------------------------------------------
    # Sharing
    # ------------------------------------------------------------------

    def get_share_url(
        self,
        obj,
    ):
        return obj.share_url

    def get_qr_payload(
        self,
        obj,
    ):
        # The client can generate the actual QR image
        # from this canonical URL.
        return obj.share_url

    def get_share_preview(
        self,
        obj,
    ):
        image_url = (
            self.get_thumbnail_url(
                obj
            )
            or self.get_cover_image_url(
                obj
            )
            or self.get_logo_url(
                obj
            )
        )

        description = (
            obj.tagline
            or obj.description
            or obj.statement_of_purpose
            or ""
        )

        return {
            "title": obj.name,
            "description": description,
            "image_url": image_url,
            "url": obj.share_url,
        }


class OrganizationWriteSerializer(
    serializers.ModelSerializer
):
    kind = serializers.ChoiceField(
        choices=OrganizationKind.choices,
    )

    # Asset selection uses public UUID instead of
    # exposing the internal database primary key.
    intro_video_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Organization

        fields = [
            # Identity
            "name",
            "short_name",
            "tagline",
            "kind",
            "founded_year",
            "activity_areas",

            # About
            "description",
            "history",
            "statement_of_faith",
            "statement_of_purpose",

            # Visual identity
            "logo",
            "cover_image",
            "thumbnail",
            "brand_color",
            "intro_video_public_id",

            # Primary contact
            "public_email",
            "public_phone_number",
            "website_url",

            # Location
            "country",
            "province_region",
            "city",
            "postal_code",
            "address_line1",
            "address_line2",
            "latitude",
            "longitude",
            "location_url",

            # Service / visiting
            "service_delivery_mode",
            "visit_instructions",
            "appointment_url",
            "contact_form_url",

            # Language
            "primary_language",
            "secondary_language",
            "timezone",

            # Visibility
            "visibility",
        ]

        extra_kwargs = {
            "name": {
                "required": True,
            },
            "kind": {
                "required": True,
            },
        }

    def validate_name(
        self,
        value,
    ):
        normalized = " ".join(
            str(
                value or ""
            ).split()
        )

        if not normalized:
            raise serializers.ValidationError(
                "Organization name is required."
            )

        return normalized

    def validate_activity_areas(
        self,
        value,
    ):
        try:
            return (
                Organization
                ._normalize_activity_areas(
                    value
                )
            )

        except DjangoValidationError as exc:
            if hasattr(
                exc,
                "message_dict",
            ):
                messages = (
                    exc.message_dict.get(
                        "activity_areas"
                    )
                )

                if messages:
                    raise (
                        serializers.ValidationError(
                            messages
                        )
                    ) from exc

            raise serializers.ValidationError(
                exc.messages
            ) from exc

    def validate(
        self,
        attrs,
    ):
        attrs = super().validate(
            attrs
        )

        marker = object()

        intro_video_public_id = (
            attrs.pop(
                "intro_video_public_id",
                marker,
            )
        )

        # Field was not supplied during PATCH.
        if (
            intro_video_public_id
            is marker
        ):
            return attrs

        # Explicit null removes the intro video.
        if (
            intro_video_public_id
            is None
        ):
            attrs["intro_video"] = None

            return attrs

        # Media assets belong to an already-created organization.
        if self.instance is None:
            raise serializers.ValidationError({
                "intro_video_public_id": (
                    "Create the organization first, "
                    "then assign its intro video."
                ),
            })

        try:
            asset = (
                OrganizationMediaAsset.objects
                .get(
                    public_id=(
                        intro_video_public_id
                    )
                )
            )

        except OrganizationMediaAsset.DoesNotExist:
            raise serializers.ValidationError({
                "intro_video_public_id": (
                    "Organization media asset "
                    "was not found."
                ),
            })

        if (
            asset.organization_id
            != self.instance.pk
        ):
            raise serializers.ValidationError({
                "intro_video_public_id": (
                    "Intro video must belong "
                    "to this organization."
                ),
            })

        if (
            str(
                getattr(
                    asset,
                    "kind",
                    "",
                )
            ).lower()
            != "video"
        ):
            raise serializers.ValidationError({
                "intro_video_public_id": (
                    "Selected organization media "
                    "asset must be a video."
                ),
            })

        if (
            str(
                getattr(
                    asset,
                    "status",
                    "",
                )
            ).lower()
            != "ready"
        ):
            raise serializers.ValidationError({
                "intro_video_public_id": (
                    "Selected intro video must "
                    "be ready before use."
                ),
            })

        attrs["intro_video"] = asset

        return attrs


class OrganizationReferenceSerializer(
    serializers.ModelSerializer
):
    """
    Stable compact Organization reference payload.

    Transport field names are retained for compatibility
    with existing Store and Payment clients.
    """

    org_name = serializers.CharField(
        source="name",
        read_only=True,
    )

    organization_logo = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = Organization

        fields = [
            "id",
            "org_name",
            "organization_logo",
            "slug",
        ]

        read_only_fields = fields

    def get_organization_logo(
        self,
        obj,
    ):
        return _organization_logo_url(
            obj,
            request=self.context.get(
                "request"
            ),
        )
# apps/organizations/modules/worship/views.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-07.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audio_catalog.models import (
    AudioCatalog,
    AudioContributor,
)
from apps.organizations.modules.worship.constants import (
    WORSHIP_PERMISSION_DEFINITIONS,
    WorshipPermissionKey,
)
from apps.organizations.modules.worship.models import (
    OrganizationMusicContribution,
    OrganizationMusicLicense,
    OrganizationRightsParty,
    WorshipWorkspace,
)
from apps.organizations.modules.worship.selectors.music import (
    list_organization_music_contributions,
    list_organization_music_licenses,
)
from apps.organizations.modules.worship.serializers import (
    WorshipArtworkSerializer,
    WorshipArtworkUploadSerializer,
    WorshipAudioUploadSerializer,
    WorshipCatalogChoiceSerializer,
    WorshipContributionCreateSerializer,
    WorshipContributionSerializer,
    WorshipContributorChoiceSerializer,
    WorshipEvidenceCreateSerializer,
    WorshipEvidenceSerializer,
    WorshipLicenseCreateSerializer,
    WorshipLicenseSerializer,
    WorshipRevokeSerializer,
    WorshipRightsPartyCreateSerializer,
    WorshipRightsPartySerializer,
    WorshipVariantSerializer,
)
from apps.organizations.modules.worship.services.access import (
    ensure_worship_permission,
    user_has_worship_permission,
)
from apps.organizations.modules.worship.services.contributions import (
    create_organization_music_contribution,
    publish_organization_music_contribution,
    revoke_organization_music_contribution,
)
from apps.organizations.modules.worship.services.licenses import (
    activate_organization_music_license,
    add_organization_music_license_evidence,
    create_organization_music_license,
    revoke_organization_music_license,
)
from apps.organizations.modules.worship.services.media import (
    add_organization_music_artwork,
    add_organization_music_variant,
)
from apps.organizations.modules.worship.services.rights import (
    create_organization_rights_party,
    deactivate_organization_rights_party,
)
from apps.organizations.permissions import (
    OrganizationsEnabledPermission,
)
from apps.organizations.services.modules import (
    get_organization_module_access,
)


class WorshipAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        OrganizationsEnabledPermission,
    ]

    def workspace(self):
        if not hasattr(self, "_worship_workspace"):
            self._worship_workspace = get_object_or_404(
                WorshipWorkspace.objects.select_related(
                    "activation__organization",
                    "activation__module",
                ),
                activation__organization__slug=self.kwargs["slug"],
            )

        return self._worship_workspace

    def run_service(self, callback, **kwargs):
        try:
            return callback(**kwargs)
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise ValidationError(
                    exc.message_dict
                ) from exc

            raise ValidationError(
                exc.messages
            ) from exc
        except ValueError as exc:
            raise ValidationError(
                str(exc)
            ) from exc


class WorshipBootstrapView(WorshipAPIView):
    def get(self, request, slug):
        workspace = self.workspace()

        ensure_worship_permission(
            actor=request.user,
            workspace=workspace,
            permission_key=WorshipPermissionKey.VIEW_MUSIC,
            require_write=False,
        )

        access = get_organization_module_access(
            organization=workspace.organization,
            module_key="worship",
            actor=request.user,
        )

        permissions = {
            key: user_has_worship_permission(
                user=request.user,
                workspace=workspace,
                permission_key=key,
            )
            for key, _, _, _ in WORSHIP_PERMISSION_DEFINITIONS
        }

        return Response({
            "workspace_id": str(workspace.public_id),
            "organization_id": str(
                workspace.organization.public_id
            ),
            "access_mode": access.access_mode,
            "reason": access.reason,
            "permissions": permissions,
            "counts": {
                "rights_parties": workspace.rights_parties.count(),
                "licenses": workspace.music_licenses.count(),
                "contributions": workspace.music_contributions.count(),
            },
        })


class WorshipRightsPartyCollectionView(WorshipAPIView):
    def get(self, request, slug):
        workspace = self.workspace()

        ensure_worship_permission(
            actor=request.user,
            workspace=workspace,
            permission_key=WorshipPermissionKey.MANAGE_RIGHTS,
            require_write=False,
        )

        queryset = (
            workspace.rights_parties
            .select_related("rights_party")
            .order_by(
                "rights_party__display_name",
                "id",
            )
        )

        return Response(
            WorshipRightsPartySerializer(
                queryset,
                many=True,
            ).data
        )

    def post(self, request, slug):
        workspace = self.workspace()
        serializer = WorshipRightsPartyCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        link = self.run_service(
            create_organization_rights_party,
            workspace=workspace,
            actor=request.user,
            **serializer.validated_data,
        )

        return Response(
            WorshipRightsPartySerializer(link).data,
            status=status.HTTP_201_CREATED,
        )


class WorshipRightsPartyDeactivateView(WorshipAPIView):
    def post(self, request, slug, public_id):
        workspace = self.workspace()

        link = get_object_or_404(
            OrganizationRightsParty,
            workspace=workspace,
            public_id=public_id,
        )

        link = self.run_service(
            deactivate_organization_rights_party,
            link=link,
            actor=request.user,
        )

        return Response(
            WorshipRightsPartySerializer(link).data
        )


class WorshipLicenseCollectionView(WorshipAPIView):
    def get(self, request, slug):
        workspace = self.workspace()

        queryset = list_organization_music_licenses(
            workspace=workspace,
            actor=request.user,
        )

        return Response(
            WorshipLicenseSerializer(
                queryset,
                many=True,
            ).data
        )

    def post(self, request, slug):
        workspace = self.workspace()
        serializer = WorshipLicenseCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        data = dict(serializer.validated_data)

        licensor = get_object_or_404(
            OrganizationRightsParty,
            workspace=workspace,
            public_id=data.pop("licensor_id"),
        )

        master_owner_id = data.pop(
            "master_owner_id",
            None,
        )

        composition_owner_id = data.pop(
            "composition_owner_id",
            None,
        )

        master_owner = (
            get_object_or_404(
                OrganizationRightsParty,
                workspace=workspace,
                public_id=master_owner_id,
            )
            if master_owner_id
            else None
        )

        composition_owner = (
            get_object_or_404(
                OrganizationRightsParty,
                workspace=workspace,
                public_id=composition_owner_id,
            )
            if composition_owner_id
            else None
        )

        license_obj = self.run_service(
            create_organization_music_license,
            workspace=workspace,
            actor=request.user,
            licensor=licensor,
            master_owner=master_owner,
            composition_owner=composition_owner,
            territory_mode="worldwide",
            territory_codes=[],
            standalone_download_allowed=False,
            external_export_allowed=False,
            **data,
        )

        return Response(
            WorshipLicenseSerializer(
                license_obj
            ).data,
            status=status.HTTP_201_CREATED,
        )


class WorshipLicenseEvidenceView(WorshipAPIView):
    def get(self, request, slug, public_id):
        workspace = self.workspace()

        license_obj = get_object_or_404(
            OrganizationMusicLicense,
            workspace=workspace,
            public_id=public_id,
        )

        ensure_worship_permission(
            actor=request.user,
            workspace=workspace,
            permission_key=WorshipPermissionKey.MANAGE_LICENSES,
            require_write=False,
        )

        return Response(
            WorshipEvidenceSerializer(
                license_obj.evidence_items.all(),
                many=True,
            ).data
        )

    def post(self, request, slug, public_id):
        workspace = self.workspace()

        license_obj = get_object_or_404(
            OrganizationMusicLicense,
            workspace=workspace,
            public_id=public_id,
        )

        serializer = WorshipEvidenceCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        evidence = self.run_service(
            add_organization_music_license_evidence,
            license=license_obj,
            actor=request.user,
            **serializer.validated_data,
        )

        return Response(
            WorshipEvidenceSerializer(
                evidence
            ).data,
            status=status.HTTP_201_CREATED,
        )


class WorshipLicenseActivateView(WorshipAPIView):
    def post(self, request, slug, public_id):
        workspace = self.workspace()

        license_obj = get_object_or_404(
            OrganizationMusicLicense,
            workspace=workspace,
            public_id=public_id,
        )

        license_obj = self.run_service(
            activate_organization_music_license,
            license=license_obj,
            actor=request.user,
        )

        return Response(
            WorshipLicenseSerializer(
                license_obj
            ).data
        )


class WorshipLicenseRevokeView(WorshipAPIView):
    def post(self, request, slug, public_id):
        workspace = self.workspace()

        license_obj = get_object_or_404(
            OrganizationMusicLicense,
            workspace=workspace,
            public_id=public_id,
        )

        serializer = WorshipRevokeSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        license_obj = self.run_service(
            revoke_organization_music_license,
            license=license_obj,
            actor=request.user,
            reason=serializer.validated_data[
                "reason"
            ],
        )

        return Response(
            WorshipLicenseSerializer(
                license_obj
            ).data
        )


class WorshipContributionCollectionView(WorshipAPIView):
    def get(self, request, slug):
        workspace = self.workspace()

        queryset = (
            list_organization_music_contributions(
                workspace=workspace,
                actor=request.user,
            )
            .prefetch_related(
                "track__artworks",
                "track__variants",
            )
        )

        return Response(
            WorshipContributionSerializer(
                queryset,
                many=True,
            ).data
        )

    def post(self, request, slug):
        workspace = self.workspace()

        serializer = WorshipContributionCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        data = dict(serializer.validated_data)

        license_obj = get_object_or_404(
            OrganizationMusicLicense,
            workspace=workspace,
            public_id=data.pop("license_id"),
        )

        catalog = get_object_or_404(
            AudioCatalog,
            public_id=data.pop("catalog_id"),
            is_active=True,
        )

        artist = get_object_or_404(
            AudioContributor,
            public_id=data.pop("primary_artist_id"),
            is_active=True,
        )

        contribution = self.run_service(
            create_organization_music_contribution,
            workspace=workspace,
            license=license_obj,
            actor=request.user,
            catalog=catalog,
            primary_artist=artist,
            **data,
        )

        return Response(
            WorshipContributionSerializer(
                contribution
            ).data,
            status=status.HTTP_201_CREATED,
        )


class WorshipContributionArtworkView(WorshipAPIView):
    def post(self, request, slug, public_id):
        workspace = self.workspace()

        contribution = get_object_or_404(
            OrganizationMusicContribution,
            workspace=workspace,
            public_id=public_id,
        )

        serializer = WorshipArtworkUploadSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        artwork = self.run_service(
            add_organization_music_artwork,
            contribution=contribution,
            actor=request.user,
            **serializer.validated_data,
        )

        return Response(
            WorshipArtworkSerializer(
                artwork
            ).data,
            status=status.HTTP_201_CREATED,
        )


class WorshipContributionAudioView(WorshipAPIView):
    def post(self, request, slug, public_id):
        workspace = self.workspace()

        contribution = get_object_or_404(
            OrganizationMusicContribution,
            workspace=workspace,
            public_id=public_id,
        )

        serializer = WorshipAudioUploadSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        variant = self.run_service(
            add_organization_music_variant,
            contribution=contribution,
            actor=request.user,
            **serializer.validated_data,
        )

        return Response(
            WorshipVariantSerializer(
                variant
            ).data,
            status=status.HTTP_201_CREATED,
        )


class WorshipContributionPublishView(WorshipAPIView):
    def post(self, request, slug, public_id):
        workspace = self.workspace()

        contribution = get_object_or_404(
            OrganizationMusicContribution,
            workspace=workspace,
            public_id=public_id,
        )

        contribution = self.run_service(
            publish_organization_music_contribution,
            contribution=contribution,
            actor=request.user,
        )

        return Response(
            WorshipContributionSerializer(
                contribution
            ).data
        )


class WorshipContributionRevokeView(WorshipAPIView):
    def post(self, request, slug, public_id):
        workspace = self.workspace()

        contribution = get_object_or_404(
            OrganizationMusicContribution,
            workspace=workspace,
            public_id=public_id,
        )

        serializer = WorshipRevokeSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        contribution = self.run_service(
            revoke_organization_music_contribution,
            contribution=contribution,
            actor=request.user,
            reason=serializer.validated_data[
                "reason"
            ],
        )

        return Response(
            WorshipContributionSerializer(
                contribution
            ).data
        )


class WorshipMusicChoicesView(WorshipAPIView):
    def get(self, request, slug):
        workspace = self.workspace()

        ensure_worship_permission(
            actor=request.user,
            workspace=workspace,
            permission_key=WorshipPermissionKey.MANAGE_CONTRIBUTIONS,
            require_write=False,
        )

        catalogs = AudioCatalog.objects.filter(
            is_active=True
        ).order_by(
            "sort_order",
            "name",
        )[:100]

        contributors = AudioContributor.objects.filter(
            is_active=True
        ).order_by(
            "display_name",
            "id",
        )[:200]

        return Response({
            "catalogs": WorshipCatalogChoiceSerializer(
                catalogs,
                many=True,
            ).data,
            "contributors": WorshipContributorChoiceSerializer(
                contributors,
                many=True,
            ).data,
        })
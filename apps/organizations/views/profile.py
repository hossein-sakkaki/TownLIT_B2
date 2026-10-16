# apps/organizations/views/profile.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-28.

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import serializers, status, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models.social import SocialMediaLink, SocialMediaType
from apps.organizations.constants import (
    CURRENT_MEMBERSHIP_STATUSES,
    OrganizationMembershipStatus,
    OrganizationPermissionKey,
    OrganizationRepresentativeStatus,
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.models import (
    Organization,
    OrganizationBusinessHour,
    OrganizationContactPoint,
    OrganizationMembership,
    OrganizationRepresentative,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.serializers.profile import (
    OrganizationBusinessHourSerializer,
    OrganizationContactPointSerializer,
    OrganizationRepresentativeCandidateSerializer,
    OrganizationRepresentativeCreateSerializer,
    OrganizationRepresentativeResponseSerializer,
    OrganizationRepresentativeSerializer,
    OrganizationSocialLinkSerializer,
    OrganizationSocialLinkWriteSerializer,
    OrganizationSocialMediaTypeSerializer,
)
from apps.organizations.services.access import user_has_organization_permission
from apps.organizations.services.profile_details import (
    create_contact_point,
    create_social_link,
    delete_contact_point,
    delete_social_link,
    invite_representative,
    remove_representative,
    replace_business_hours,
    respond_to_representative_invitation,
    update_contact_point,
    update_social_link,
)

from .helpers import raise_drf_validation_error


PROFILE_PERMISSIONS = [IsAuthenticated, OrganizationsEnabledPermission]


def _get_organization(*, request, slug):
    organization = get_object_or_404(Organization, slug=slug)

    if getattr(request.user, "is_staff", False):
        return organization

    publicly_available = (
        organization.status == OrganizationStatus.ACTIVE
        and organization.visibility in {
            OrganizationVisibility.PUBLIC,
            OrganizationVisibility.UNLISTED,
        }
    )
    if publicly_available:
        return organization

    member_access = OrganizationMembership.objects.filter(
        organization=organization,
        member__user=request.user,
        status__in=CURRENT_MEMBERSHIP_STATUSES,
    ).exists()

    if member_access:
        return organization

    raise NotFound("Organization not found.")


def _can_manage(*, request, organization):
    return user_has_organization_permission(
        user=request.user,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_PROFILE,
    )


class OrganizationProfileBaseViewSet(viewsets.ViewSet):
    permission_classes = PROFILE_PERMISSIONS

    def get_organization(self):
        return _get_organization(
            request=self.request,
            slug=self.kwargs["slug"],
        )

    def can_manage(self, organization=None):
        return _can_manage(
            request=self.request,
            organization=organization or self.get_organization(),
        )


class OrganizationContactPointsView(OrganizationProfileBaseViewSet):
    def list(self, request, slug=None):
        organization = self.get_organization()
        queryset = OrganizationContactPoint.objects.filter(organization=organization)

        if not self.can_manage(organization):
            queryset = queryset.filter(is_public=True)

        queryset = queryset.order_by("-is_primary", "sort_order", "id")
        return Response(OrganizationContactPointSerializer(queryset, many=True).data)

    def create(self, request, slug=None):
        organization = self.get_organization()
        serializer = OrganizationContactPointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            contact = create_contact_point(
                organization=organization,
                actor=request.user,
                validated_data=serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationContactPointSerializer(contact).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationContactPointDetailView(OrganizationProfileBaseViewSet):
    def get_contact(self):
        return get_object_or_404(
            OrganizationContactPoint,
            organization=self.get_organization(),
            public_id=self.kwargs["public_id"],
        )

    def partial_update(self, request, slug=None, public_id=None):
        contact = self.get_contact()
        serializer = OrganizationContactPointSerializer(
            contact,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        try:
            contact = update_contact_point(
                contact=contact,
                actor=request.user,
                validated_data=serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(OrganizationContactPointSerializer(contact).data)

    def destroy(self, request, slug=None, public_id=None):
        delete_contact_point(contact=self.get_contact(), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationBusinessHoursView(OrganizationProfileBaseViewSet):
    def list(self, request, slug=None):
        organization = self.get_organization()
        queryset = OrganizationBusinessHour.objects.filter(
            organization=organization
        ).order_by("weekday", "sort_order", "id")

        return Response(
            OrganizationBusinessHourSerializer(queryset, many=True).data
        )

    def replace(self, request, slug=None):
        organization = self.get_organization()
        serializer = OrganizationBusinessHourSerializer(
            data=request.data,
            many=True,
        )
        serializer.is_valid(raise_exception=True)

        try:
            queryset = replace_business_hours(
                organization=organization,
                actor=request.user,
                validated_rows=serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationBusinessHourSerializer(queryset, many=True).data
        )


class OrganizationRepresentativeCandidatesView(OrganizationProfileBaseViewSet):
    def list(self, request, slug=None):
        organization = self.get_organization()

        if not self.can_manage(organization):
            raise PermissionDenied(
                "You do not have permission to manage representatives."
            )

        query = str(request.query_params.get("q", "")).strip()

        queryset = OrganizationMembership.objects.select_related(
            "member__user"
        ).filter(
            organization=organization,
            status=OrganizationMembershipStatus.ACTIVE,
            member__is_active=True,
            member__user__is_active=True,
        )

        if query:
            queryset = queryset.filter(
                Q(member__user__username__icontains=query)
                | Q(member__user__name__icontains=query)
                | Q(member__user__family__icontains=query)
            )

        queryset = queryset.order_by(
            "member__user__name",
            "member__user__family",
            "id",
        )[:30]

        return Response(
            OrganizationRepresentativeCandidateSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )


class OrganizationRepresentativesView(OrganizationProfileBaseViewSet):
    def list(self, request, slug=None):
        organization = self.get_organization()

        queryset = OrganizationRepresentative.objects.select_related(
            "membership__member__user"
        ).filter(organization=organization)

        if not self.can_manage(organization):
            queryset = queryset.filter(
                status=OrganizationRepresentativeStatus.ACCEPTED,
                membership__status=OrganizationMembershipStatus.ACTIVE,
                membership__member__is_active=True,
                membership__member__user__is_active=True,
            )

        queryset = queryset.order_by("-is_primary", "sort_order", "id")

        return Response(
            OrganizationRepresentativeSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def create(self, request, slug=None):
        organization = self.get_organization()
        serializer = OrganizationRepresentativeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            representative = invite_representative(
                organization=organization,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationRepresentativeSerializer(
                representative,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationRepresentativeResponseView(OrganizationProfileBaseViewSet):
    def respond(self, request, slug=None, public_id=None):
        organization = self.get_organization()
        representative = get_object_or_404(
            OrganizationRepresentative,
            organization=organization,
            public_id=public_id,
        )

        serializer = OrganizationRepresentativeResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            representative = respond_to_representative_invitation(
                representative=representative,
                actor=request.user,
                decision=serializer.validated_data["decision"],
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationRepresentativeSerializer(
                representative,
                context={"request": request},
            ).data
        )


class OrganizationRepresentativeDetailView(OrganizationProfileBaseViewSet):
    def destroy(self, request, slug=None, public_id=None):
        organization = self.get_organization()
        representative = get_object_or_404(
            OrganizationRepresentative,
            organization=organization,
            public_id=public_id,
        )

        remove_representative(
            representative=representative,
            actor=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationSocialLinksView(OrganizationProfileBaseViewSet):
    def list(self, request, slug=None):
        organization = self.get_organization()
        content_type = ContentType.objects.get_for_model(
            Organization,
            for_concrete_model=False,
        )

        queryset = SocialMediaLink.objects.select_related(
            "social_media_type"
        ).filter(
            content_type=content_type,
            object_id=organization.pk,
        )

        if not self.can_manage(organization):
            queryset = queryset.filter(
                is_active=True,
                social_media_type__is_active=True,
            )

        return Response(
            OrganizationSocialLinkSerializer(queryset, many=True).data
        )

    def create(self, request, slug=None):
        organization = self.get_organization()
        serializer = OrganizationSocialLinkWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            social_link = create_social_link(
                organization=organization,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationSocialLinkSerializer(social_link).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationSocialLinkDetailView(OrganizationProfileBaseViewSet):
    def get_link(self):
        organization = self.get_organization()
        content_type = ContentType.objects.get_for_model(
            Organization,
            for_concrete_model=False,
        )

        return get_object_or_404(
            SocialMediaLink,
            pk=self.kwargs["link_id"],
            content_type=content_type,
            object_id=organization.pk,
        )

    def partial_update(self, request, slug=None, link_id=None):
        organization = self.get_organization()
        social_link = self.get_link()
        validated_data = {}

        if "link" in request.data:
            validated_data["link"] = serializers.URLField(
                max_length=500
            ).run_validation(request.data["link"])

        if "is_active" in request.data:
            validated_data["is_active"] = serializers.BooleanField().run_validation(
                request.data["is_active"]
            )

        try:
            social_link = update_social_link(
                organization=organization,
                actor=request.user,
                social_link=social_link,
                validated_data=validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(OrganizationSocialLinkSerializer(social_link).data)

    def destroy(self, request, slug=None, link_id=None):
        organization = self.get_organization()
        social_link = self.get_link()

        delete_social_link(
            organization=organization,
            actor=request.user,
            social_link=social_link,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationSocialMediaTypesView(OrganizationProfileBaseViewSet):
    def list(self, request, slug=None):
        organization = self.get_organization()

        if not self.can_manage(organization):
            raise PermissionDenied(
                "You do not have permission to manage organization social links."
            )

        content_type = ContentType.objects.get_for_model(
            Organization,
            for_concrete_model=False,
        )

        used_type_ids = SocialMediaLink.objects.filter(
            content_type=content_type,
            object_id=organization.pk,
        ).values_list("social_media_type_id", flat=True)

        queryset = SocialMediaType.objects.filter(
            is_active=True
        ).exclude(
            id__in=used_type_ids
        ).order_by("name", "id")

        return Response(
            OrganizationSocialMediaTypeSerializer(queryset, many=True).data
        )
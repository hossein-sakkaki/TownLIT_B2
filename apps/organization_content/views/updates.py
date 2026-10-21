# apps/organization_content/views/updates.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-28.
# Last Update by Hossein Sakkaki on 2026-10-20.

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404

from rest_framework import serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.organization_content.models import OrganizationUpdate
from apps.organization_content.services.publication import (request_update_publication, discard_unsubmitted_update)
from apps.organization_content.serializers import (
    OrganizationUpdateCreateSerializer,
    OrganizationUpdateHomeVisibilitySerializer,
    OrganizationUpdatePatchSerializer,
    OrganizationUpdatePublishSerializer,
    OrganizationUpdateSerializer,
)
from apps.organization_content.services.updates import (
    archive_update,
    create_update,
    publish_update,
    set_update_home_visibility,
    update_update,
)
from apps.organizations.constants import OrganizationPermissionKey
from apps.organizations.models import Organization
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organization_content.services.access import can_manage_content
from apps.organizations.views.helpers import raise_drf_validation_error


class OrganizationUpdateViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get_organization(self):
        if hasattr(self, "_organization"):
            return self._organization

        self._organization = get_object_or_404(
            Organization,
            slug=self.kwargs["slug"],
        )
        return self._organization

    def ensure_manager(self):
        organization = self.get_organization()

        if not can_manage_content(actor=self.request.user, organization=organization):
            raise PermissionDenied(
                "You do not have permission to manage Organization updates."
            )

        return organization

    def get_update(self):
        organization = self.ensure_manager()

        return get_object_or_404(
            OrganizationUpdate.objects.select_related(
                "organization"
            ).prefetch_related(
                "media_items__asset"
            ),
            organization=organization,
            public_id=self.kwargs["public_id"],
        )

    def list(self, request, slug=None):
        organization = self.ensure_manager()

        queryset = OrganizationUpdate.objects.select_related(
            "organization"
        ).prefetch_related(
            "media_items__asset"
        ).filter(
            organization=organization
        )

        status_value = request.query_params.get("status")

        if status_value:
            status_value = serializers.ChoiceField(
                choices=OrganizationUpdate.Status.choices
            ).run_validation(status_value)

            queryset = queryset.filter(
                status=status_value
            )

        queryset = queryset.order_by(
            "-created_at",
            "-pk",
        )

        return Response(
            OrganizationUpdateSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def retrieve(self, request, slug=None, public_id=None):
        return Response(
            OrganizationUpdateSerializer(
                self.get_update(),
                context={"request": request},
            ).data
        )

    def create(self, request, slug=None):
        organization = self.ensure_manager()

        serializer = OrganizationUpdateCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            update = create_update(
                organization=organization,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        update = OrganizationUpdate.objects.select_related(
            "organization"
        ).prefetch_related(
            "media_items__asset"
        ).get(pk=update.pk)

        return Response(
            OrganizationUpdateSerializer(
                update,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, slug=None, public_id=None):
        update = self.get_update()

        serializer = OrganizationUpdatePatchSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        try:
            update = update_update(
                update=update,
                actor=request.user,
                validated_data=serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        update = OrganizationUpdate.objects.select_related(
            "organization"
        ).prefetch_related(
            "media_items__asset"
        ).get(pk=update.pk)

        return Response(
            OrganizationUpdateSerializer(
                update,
                context={"request": request},
            ).data
        )

    def publish(self, request, slug=None, public_id=None):
        update = self.get_update()

        serializer = OrganizationUpdatePublishSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            update = publish_update(
                update=update,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        update = OrganizationUpdate.objects.select_related(
            "organization"
        ).prefetch_related(
            "media_items__asset"
        ).get(pk=update.pk)

        return Response(
            OrganizationUpdateSerializer(
                update,
                context={"request": request},
            ).data
        )

    def archive(self, request, slug=None, public_id=None):
        update = self.get_update()

        try:
            update = archive_update(
                update=update,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationUpdateSerializer(
                update,
                context={"request": request},
            ).data
        )

    def home_visibility(self, request, slug=None, public_id=None):
        update = self.get_update()

        serializer = OrganizationUpdateHomeVisibilitySerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            set_update_home_visibility(
                update=update,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        update = OrganizationUpdate.objects.select_related(
            "organization"
        ).prefetch_related(
            "media_items__asset"
        ).get(pk=update.pk)

        return Response(
            OrganizationUpdateSerializer(
                update,
                context={"request": request},
            ).data
        )


    def submit(self, request, slug=None, public_id=None):
        update = self.get_update()
        try:
            update = request_update_publication(update=update, actor=request.user)
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)
        return Response(OrganizationUpdateSerializer(
            update, context={"request": request},
        ).data, status=status.HTTP_202_ACCEPTED)

    def discard(self, request, slug=None, public_id=None):
        update = self.get_update()
        try:
            discard_unsubmitted_update(update=update, actor=request.user)
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)

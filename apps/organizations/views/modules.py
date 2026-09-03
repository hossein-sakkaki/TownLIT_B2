# apps/organizations/views/modules.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    OrganizationModuleActivationStatus,
    OrganizationModuleVisibility,
    OrganizationPermissionKey,
)
from apps.organizations.models import OrganizationModuleActivation
from apps.organizations.feature_flags import organization_modules_enabled
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.selectors.modules import organization_module_catalog_queryset
from apps.organizations.serializers import (
    OrganizationModuleAccessSerializer,
    OrganizationModuleActivationSerializer,
    OrganizationModuleActivationWriteSerializer,
    OrganizationModuleDefinitionSerializer,
    OrganizationModuleSuspensionSerializer,
)
from apps.organizations.services.access import (
    get_current_membership_for_user,
    user_has_organization_permission,
)
from apps.organizations.services.modules import (
    activate_organization_module,
    disable_organization_module,
    get_organization_module_access,
    restore_suspended_organization_module,
    suspend_organization_module,
    update_organization_module_profile,
)

from .access import get_visible_organization_or_404
from .helpers import raise_drf_validation_error


def _get_activation(organization, module_key):
    activation = (
        OrganizationModuleActivation.objects
        .select_related("module", "organization")
        .filter(
            organization=organization,
            module__key=module_key,
        )
        .first()
    )
    if not activation:
        raise NotFound("Organization module activation not found.")
    return activation


def _access_payload(access):
    definition = access.definition
    activation = access.activation
    return {
        "key": access.module_key,
        "name": definition.name if definition else access.module_key,
        "description": definition.description if definition else None,
        "status": activation.status if activation else None,
        "visibility": activation.visibility if activation else None,
        "access_mode": access.access_mode,
        "reason": access.reason,
        "is_verified": access.is_verified,
        "has_entitlement": access.has_entitlement,
        "can_manage": access.can_manage,
        "can_write": access.can_write,
        "activated": activation is not None,
        "activation_public_id": activation.public_id if activation else None,
        "display_name": activation.display_name if activation else None,
        "summary": activation.summary if activation else None,
        "schema_version": definition.schema_version if definition else 1,
    }


def _can_view_module_payload(*, item, user, organization):
    if getattr(user, "is_staff", False):
        return True

    if user_has_organization_permission(
        user=user,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_MODULES,
    ):
        return True

    if item["can_manage"]:
        return True

    if not item["activated"]:
        return False

    if item["status"] != OrganizationModuleActivationStatus.ENABLED:
        return False

    if item["visibility"] == OrganizationModuleVisibility.PUBLIC:
        return True

    membership = get_current_membership_for_user(
        organization=organization,
        user=user,
    )
    is_active_member = bool(
        membership
        and membership.status in ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES
    )

    return bool(
        is_active_member
        and item["visibility"] == OrganizationModuleVisibility.MEMBERS_ONLY
    )


def _public_safe_module_payload(*, item, user, organization):
    can_manage = bool(
        getattr(user, "is_staff", False)
        or item["can_manage"]
        or user_has_organization_permission(
            user=user,
            organization=organization,
            permission_key=OrganizationPermissionKey.MANAGE_MODULES,
        )
    )

    if not can_manage:
        item = dict(item)
        item["has_entitlement"] = None

    return item


class OrganizationModuleCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not organization_modules_enabled():
            return Response([])

        queryset = organization_module_catalog_queryset(public_only=True)
        return Response(
            OrganizationModuleDefinitionSerializer(
                queryset,
                many=True,
            ).data
        )


class OrganizationModulesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        definitions = organization_module_catalog_queryset(public_only=False)
        payload = [
            _access_payload(
                get_organization_module_access(
                    organization=organization,
                    module_key=definition.key,
                    actor=request.user,
                )
            )
            for definition in definitions
        ]

        visible = [
            _public_safe_module_payload(
                item=item,
                user=request.user,
                organization=organization,
            )
            for item in payload
            if _can_view_module_payload(
                item=item,
                user=request.user,
                organization=organization,
            )
        ]

        return Response(
            OrganizationModuleAccessSerializer(
                visible,
                many=True,
            ).data
        )


class OrganizationModuleDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, module_key):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        access = get_organization_module_access(
            organization=organization,
            module_key=module_key,
            actor=request.user,
        )
        item = _access_payload(access)

        if not _can_view_module_payload(
            item=item,
            user=request.user,
            organization=organization,
        ):
            raise NotFound("Organization module not found.")

        item = _public_safe_module_payload(
            item=item,
            user=request.user,
            organization=organization,
        )
        return Response(
            OrganizationModuleAccessSerializer(item).data
        )

    def patch(self, request, slug, module_key):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        activation = _get_activation(organization, module_key)
        serializer = OrganizationModuleActivationWriteSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        try:
            data = serializer.validated_data
            activation = update_organization_module_profile(
                activation=activation,
                actor=request.user,
                display_name=data.get(
                    "display_name",
                    activation.display_name,
                ),
                summary=data.get(
                    "summary",
                    activation.summary,
                ),
                visibility=data.get(
                    "visibility",
                    activation.visibility,
                ),
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationModuleActivationSerializer(
                activation,
                context={"request": request},
            ).data
        )


class OrganizationModuleActivateView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, module_key):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        serializer = OrganizationModuleActivationWriteSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            activation = activate_organization_module(
                organization=organization,
                module_key=module_key,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationModuleActivationSerializer(
                activation,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


class OrganizationModuleDisableView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, module_key):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        activation = _get_activation(organization, module_key)

        try:
            activation = disable_organization_module(
                activation=activation,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationModuleActivationSerializer(
                activation,
                context={"request": request},
            ).data
        )


class OrganizationModuleSuspendView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, module_key):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        activation = _get_activation(organization, module_key)
        serializer = OrganizationModuleSuspensionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        activation = suspend_organization_module(
            activation=activation,
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )

        return Response(
            OrganizationModuleActivationSerializer(
                activation,
                context={"request": request},
            ).data
        )


class OrganizationModuleRestoreView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, module_key):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        activation = _get_activation(organization, module_key)
        activation = restore_suspended_organization_module(
            activation=activation,
            actor=request.user,
        )
        return Response(
            OrganizationModuleActivationSerializer(
                activation,
                context={"request": request},
            ).data
        )

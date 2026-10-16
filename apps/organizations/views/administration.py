# apps/organizations/views/administration.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-01.
# Last Update by Hossein Sakkaki on 2026-10-01.
#

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.constants import (
    OrganizationAuditSource,
    OrganizationMembershipStatus,
    OrganizationPermissionKey,
)
from apps.organizations.models import OrganizationAuditLog
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.serializers import (
    OrganizationAdministrationOverviewSerializer,
    OrganizationAuditLogSerializer,
)
from apps.organizations.serializers.administration import (
    CLIENT_VISIBLE_ORGANIZATION_AUDIT_ACTIONS,
    ORGANIZATION_AUDIT_CATEGORY_ACTIONS,
    organization_audit_category_choices,
    organization_audit_source_choices,
)
from apps.organizations.services.access import (
    get_current_membership_for_user,
    user_has_organization_permission,
)

from .access import get_visible_organization_or_404


DEFAULT_AUDIT_PAGE_SIZE = 30
MAX_AUDIT_PAGE_SIZE = 100


def _ensure_lifecycle_view_access(*, user, organization):
    if getattr(user, "is_staff", False):
        return

    membership = get_current_membership_for_user(
        organization=organization,
        user=user,
    )

    if not membership or membership.status != OrganizationMembershipStatus.ACTIVE:
        raise PermissionDenied(
            "You do not have access to Organization administration."
        )


def _ensure_audit_view_access(*, user, organization):
    if not user_has_organization_permission(
        user=user,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_SETTINGS,
    ):
        raise PermissionDenied(
            "You do not have permission to view Organization activity."
        )


def _parse_positive_int(value, *, field_name, default=None, maximum=None):
    if value in {None, ""}:
        return default

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({
            field_name: "A positive integer is required.",
        }) from exc

    if parsed <= 0:
        raise ValidationError({
            field_name: "A positive integer is required.",
        })

    if maximum is not None:
        parsed = min(parsed, maximum)

    return parsed


class OrganizationAdministrationOverviewView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        _ensure_lifecycle_view_access(
            user=request.user,
            organization=organization,
        )

        return Response(
            OrganizationAdministrationOverviewSerializer(
                organization,
                context={"request": request},
            ).data
        )


class OrganizationAuditActivityView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        _ensure_audit_view_access(
            user=request.user,
            organization=organization,
        )

        category = str(
            request.query_params.get("category") or ""
        ).strip().lower()
        source = str(
            request.query_params.get("source") or ""
        ).strip().lower()
        action = str(
            request.query_params.get("action") or ""
        ).strip().lower()

        if category and category not in ORGANIZATION_AUDIT_CATEGORY_ACTIONS:
            raise ValidationError({
                "category": "Unknown Organization activity category.",
            })

        valid_sources = {
            value
            for value, _ in OrganizationAuditSource.choices
        }
        if source and source not in valid_sources:
            raise ValidationError({
                "source": "Unknown Organization activity source.",
            })

        if action and action not in CLIENT_VISIBLE_ORGANIZATION_AUDIT_ACTIONS:
            raise ValidationError({
                "action": "Unknown or unavailable Organization activity action.",
            })

        before_id = _parse_positive_int(
            request.query_params.get("before_id"),
            field_name="before_id",
        )
        limit = _parse_positive_int(
            request.query_params.get("limit"),
            field_name="limit",
            default=DEFAULT_AUDIT_PAGE_SIZE,
            maximum=MAX_AUDIT_PAGE_SIZE,
        )

        queryset = (
            OrganizationAuditLog.objects
            .filter(
                organization=organization,
                action__in=CLIENT_VISIBLE_ORGANIZATION_AUDIT_ACTIONS,
            )
            .select_related(
                "actor",
                "target_user",
                "membership__member__user",
                "membership_request__member__user",
                "role_assignment__role",
                "role_assignment__membership__member__user",
                "verification_case",
                "relationship__source_organization",
                "relationship__target_organization",
                "governance_proposal",
                "module_activation__module",
            )
            .order_by("-id")
        )

        if category:
            queryset = queryset.filter(
                action__in=ORGANIZATION_AUDIT_CATEGORY_ACTIONS[category]
            )

        if source:
            queryset = queryset.filter(source=source)

        if action:
            queryset = queryset.filter(action=action)

        if before_id:
            queryset = queryset.filter(id__lt=before_id)

        rows = list(queryset[: limit + 1])
        has_more = len(rows) > limit
        page = rows[:limit]

        next_before_id = (
            page[-1].id
            if has_more and page
            else None
        )

        return Response({
            "results": OrganizationAuditLogSerializer(
                page,
                many=True,
                context={"request": request},
            ).data,
            "has_more": has_more,
            "next_before_id": next_before_id,
            "categories": organization_audit_category_choices(),
            "sources": organization_audit_source_choices(),
        })

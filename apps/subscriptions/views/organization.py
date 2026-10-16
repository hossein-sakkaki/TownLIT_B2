# apps/subscriptions/views/organization.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-01.
# Last Update by Hossein Sakkaki on 2026-10-02.
#

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.constants import OrganizationPermissionKey
from apps.organizations.services.access import user_has_organization_permission
from apps.organizations.views.access import get_visible_organization_or_404
from apps.subscriptions.constants import (
    CURRENT_SUBSCRIPTION_STATUSES,
    ORGANIZATION_SUBSCRIPTION_AUDIENCE_KEY,
)
from apps.subscriptions.selectors.plans import public_plan_queryset
from apps.subscriptions.serializers import (
    OrganizationSubscriptionAccountUpdateSerializer,
    OrganizationSubscriptionOverviewSerializer,
)
from apps.subscriptions.services.accounts import update_subscription_billing_email
from apps.subscriptions.services.eligibility import (
    resolve_subscription_account_eligibility,
)
from apps.subscriptions.services.entitlements import get_effective_entitlements


def _require_manage_billing(*, user, organization):
    if not user_has_organization_permission(
        user=user,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_BILLING,
    ):
        raise PermissionDenied(
            "You do not have permission to manage organization billing."
        )


def _current_subscription(account):
    return (
        account.subscriptions
        .filter(status__in=CURRENT_SUBSCRIPTION_STATUSES)
        .select_related("plan")
        .prefetch_related(
            "plan__prices",
            "plan__plan_entitlements__entitlement",
        )
        .first()
    )


def _overview_payload(*, organization):
    account = organization.subscription_account
    eligibility = resolve_subscription_account_eligibility(
        account=account,
    )

    return {
        "audience_key": ORGANIZATION_SUBSCRIPTION_AUDIENCE_KEY,
        "account": account,
        "eligibility": eligibility.as_dict(),
        "current_subscription": _current_subscription(account),
        "available_plans": public_plan_queryset(
            audience_key=ORGANIZATION_SUBSCRIPTION_AUDIENCE_KEY,
        ),
        "effective_entitlements": get_effective_entitlements(
            account=account,
        ),
    }


class OrganizationSubscriptionOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        _require_manage_billing(
            user=request.user,
            organization=organization,
        )

        serializer = OrganizationSubscriptionOverviewSerializer(
            _overview_payload(
                organization=organization,
            )
        )
        return Response(serializer.data)

    def patch(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        _require_manage_billing(
            user=request.user,
            organization=organization,
        )

        serializer = OrganizationSubscriptionAccountUpdateSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        if "billing_email" in serializer.validated_data:
            try:
                update_subscription_billing_email(
                    account=organization.subscription_account,
                    billing_email=serializer.validated_data.get(
                        "billing_email"
                    ),
                    actor=request.user,
                )
            except DjangoValidationError as exc:
                detail = getattr(exc, "message_dict", None)
                if detail is None:
                    detail = getattr(exc, "messages", None) or str(exc)
                raise serializers.ValidationError(detail)

        organization.subscription_account.refresh_from_db()

        response_serializer = OrganizationSubscriptionOverviewSerializer(
            _overview_payload(
                organization=organization,
            )
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

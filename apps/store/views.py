from rest_framework import status, viewsets
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response

from apps.organizations.permissions import (
    OrganizationsEnabledPermission,
)
from apps.store.services.organization_access import (
    effective_owned_organizations_queryset,
    resolve_store_create_organization,
    user_owns_organization,
)

from .models import Store
from .serializers import StoreSerializer


class StoreViewSet(
    viewsets.ModelViewSet
):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [
        IsAuthenticated,
        OrganizationsEnabledPermission,
    ]

    def get_queryset(self):
        user = self.request.user

        if getattr(
            user,
            "is_staff",
            False,
        ):
            return super().get_queryset()

        organization_ids = (
            effective_owned_organizations_queryset(
                user=user,
            )
            .values_list(
                "id",
                flat=True,
            )
        )

        return Store.objects.filter(
            organization_id__in=organization_ids,
        )

    def retrieve(
        self,
        request,
        *args,
        **kwargs,
    ):
        store = self.get_object()
        serializer = self.get_serializer(
            store
        )
        return Response(
            serializer.data
        )

    def create(
        self,
        request,
        *args,
        **kwargs,
    ):
        organization = (
            resolve_store_create_organization(
                user=request.user,
                organization_id=(
                    request.data.get(
                        "organization"
                    )
                ),
            )
        )

        serializer = self.get_serializer(
            data=request.data
        )
        serializer.is_valid(
            raise_exception=True
        )

        serializer.save(
            organization=organization
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def update(
        self,
        request,
        *args,
        **kwargs,
    ):
        store = self.get_object()

        if not user_owns_organization(
            user=request.user,
            organization=store.organization,
        ):
            return Response(
                {
                    "error": (
                        "Only organization owners "
                        "can update the store."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().update(
            request,
            *args,
            **kwargs,
        )

    def destroy(
        self,
        request,
        *args,
        **kwargs,
    ):
        store = self.get_object()

        if not user_owns_organization(
            user=request.user,
            organization=store.organization,
        ):
            return Response(
                {
                    "error": (
                        "Only organization owners "
                        "can delete the store."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().destroy(
            request,
            *args,
            **kwargs,
        )
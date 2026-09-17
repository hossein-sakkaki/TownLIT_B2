# apps/accounts/views/social_views.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models.social import (
    SocialMediaLink,
    SocialMediaType,
)
from apps.accounts.serializers.social_serializers import (
    SocialMediaLinkReadOnlySerializer,
    SocialMediaLinkSerializer,
    SocialMediaTypeSerializer,
)
from apps.accounts.services.social_links import (
    SOCIAL_OWNER_ORGANIZATION,
    SOCIAL_OWNER_USER,
    resolve_social_owner_for_management,
    social_content_type_for_key,
)


class SocialLinksViewSet(viewsets.ViewSet):
    permission_classes = [
        IsAuthenticated,
    ]

    @action(
        detail=False,
        methods=["get"],
        url_path="list",
        permission_classes=[IsAuthenticated],
    )
    def list_links(self, request):
        content_type_key = (
            request.query_params.get("content_type")
        )
        object_id = request.query_params.get(
            "object_id"
        )

        if not content_type_key or not object_id:
            return Response(
                {
                    "error": (
                        "content_type and object_id "
                        "are required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = social_content_type_for_key(
            content_type_key
        )

        if content_type is None:
            return Response(
                {
                    "error": (
                        "Invalid content_type provided."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        owner = resolve_social_owner_for_management(
            actor=request.user,
            content_type_key=content_type_key,
            object_id=object_id,
        )

        if owner is None:
            return Response(
                {
                    "error": (
                        "Access denied to these "
                        "social links."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        links = SocialMediaLink.objects.filter(
            content_type=content_type,
            object_id=owner.pk,
        )

        serializer = (
            SocialMediaLinkReadOnlySerializer(
                links,
                many=True,
                context={"request": request},
            )
        )

        return Response(
            {
                "links": serializer.data,
                "message": (
                    "Links fetched successfully."
                ),
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="add",
        permission_classes=[IsAuthenticated],
    )
    def add_link(self, request):
        content_type_key = request.data.get(
            "content_type"
        )
        object_id = request.data.get(
            "object_id"
        )
        social_media_type = request.data.get(
            "social_media_type"
        )
        link = request.data.get("link")

        if not all(
            [
                content_type_key,
                object_id,
                social_media_type,
                link,
            ]
        ):
            return Response(
                {
                    "error": (
                        "All fields are required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_object = (
            resolve_social_owner_for_management(
                actor=request.user,
                content_type_key=content_type_key,
                object_id=object_id,
            )
        )

        if content_object is None:
            return Response(
                {
                    "error": (
                        "You do not have permission "
                        "to manage social links for "
                        "this object."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = SocialMediaLinkSerializer(
            data={
                "social_media_type": (
                    social_media_type
                ),
                "link": link,
                "content_type": (
                    content_type_key
                ),
                "object_id": object_id,
            },
            context={"request": request},
        )
        serializer.is_valid(
            raise_exception=True
        )
        serializer.save()

        return Response(
            {
                "data": serializer.data,
                "message": (
                    "Social media link added "
                    "successfully."
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["delete"],
        url_path="delete",
        permission_classes=[IsAuthenticated],
    )
    def delete_link(self, request):
        link_id = request.query_params.get("id")

        if not link_id:
            return Response(
                {
                    "error": (
                        "Link ID is required "
                        "for deletion."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            link_id = int(link_id)
        except (TypeError, ValueError):
            return Response(
                {
                    "error": "Invalid Link ID."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            link = SocialMediaLink.objects.get(
                id=link_id
            )
        except SocialMediaLink.DoesNotExist:
            return Response(
                {
                    "error": "Link not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        organization_ct = (
            social_content_type_for_key(
                SOCIAL_OWNER_ORGANIZATION
            )
        )
        user_ct = social_content_type_for_key(
            SOCIAL_OWNER_USER
        )

        if (
            organization_ct is not None
            and link.content_type_id
            == organization_ct.id
        ):
            content_type_key = (
                SOCIAL_OWNER_ORGANIZATION
            )
        elif (
            user_ct is not None
            and link.content_type_id
            == user_ct.id
        ):
            content_type_key = SOCIAL_OWNER_USER
        else:
            return Response(
                {
                    "error": (
                        "You cannot delete "
                        "this link."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        owner = resolve_social_owner_for_management(
            actor=request.user,
            content_type_key=content_type_key,
            object_id=link.object_id,
        )

        if owner is None:
            return Response(
                {
                    "error": (
                        "You cannot delete "
                        "this link."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        link.delete()

        return Response(
            {
                "success": True,
                "message": (
                    "Link deleted successfully."
                ),
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="social-media-types",
        permission_classes=[IsAuthenticated],
    )
    def get_social_media_types(self, request):
        user_content_type = (
            social_content_type_for_key(
                SOCIAL_OWNER_USER
            )
        )

        used_social_media = (
            SocialMediaLink.objects
            .filter(
                content_type=user_content_type,
                object_id=request.user.id,
            )
            .values_list(
                "social_media_type",
                flat=True,
            )
        )

        available_types = (
            SocialMediaType.objects
            .filter(is_active=True)
            .exclude(id__in=used_social_media)
        )

        serializer = SocialMediaTypeSerializer(
            available_types,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
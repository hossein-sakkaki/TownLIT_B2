# apps/conversation/views/organization/direct.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.conversation.constants import OrganizationConversationStatus
from apps.conversation.permissions import ConversationAccessPermission
from apps.conversation.policies import ConversationAccessPolicy
from apps.conversation.serializers import DialogueSerializer, MessageSerializer
from apps.conversation.serializers.organization.direct import OrganizationDirectThreadSerializer
from apps.conversation.services.organization import (
    assign_organization_direct_thread,
    build_organization_direct_inbox_queryset,
    get_organization_direct_context,
    get_organization_direct_context_by_slug,
    mark_organization_direct_read_for_operator,
    organization_direct_total_unread_count,
    organization_messenger_is_available,
    organization_operator_can_view,
    send_organization_direct_participant_message,
    send_organization_direct_reply,
    transition_organization_direct_thread,
)
from apps.conversation.services.read_delivery import mark_dialogue_read_for_user
from apps.organizations.models import Organization, OrganizationMembership


class OrganizationMessengerPagination(LimitOffsetPagination):
    default_limit = 30
    max_limit = 100


def _organization(organization_slug):
    return get_object_or_404(Organization, slug=organization_slug)


def _service_error(result):
    return Response(
        {
            "error": result.get("message", "Request failed."),
            "code": result.get("code", "REQUEST_FAILED"),
        },
        status=result.get("status", status.HTTP_400_BAD_REQUEST),
    )


def _operator_forbidden():
    return Response(
        {
            "error": "Organization Messenger access is not permitted.",
            "code": "organization_messenger_forbidden",
        },
        status=status.HTTP_403_FORBIDDEN,
    )


class OrganizationDirectParticipantConversationView(APIView):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def get(self, request, organization_slug):
        organization = _organization(organization_slug)
        context = get_organization_direct_context(
            organization=organization,
            participant_user=request.user,
        )
        if context is None:
            return Response(
                {
                    "dialogue": None,
                    "messenger_available": organization_messenger_is_available(
                        organization
                    ),
                },
                status=status.HTTP_200_OK,
            )

        access = ConversationAccessPolicy.can_view(
            dialogue=context.dialogue,
            user=request.user,
        )
        if not access.allowed:
            return Response(
                {"error": access.message, "code": access.code},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                "dialogue": DialogueSerializer(
                    context.dialogue,
                    context={"request": request},
                ).data,
                "messenger_available": organization_messenger_is_available(
                    organization
                ),
            },
            status=status.HTTP_200_OK,
        )


class OrganizationDirectParticipantMessageView(APIView):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def post(self, request, organization_slug):
        organization = _organization(organization_slug)
        result = send_organization_direct_participant_message(
            organization=organization,
            participant_user=request.user,
            content=request.data.get("content"),
            reply_to_message_id=request.data.get("reply_to_message_id"),
        )
        if not result.get("ok"):
            return _service_error(result)

        payload = result["payload"]
        context = payload["context"]
        return Response(
            {
                "dialogue": DialogueSerializer(
                    context.dialogue,
                    context={"request": request},
                ).data,
                "message": MessageSerializer(
                    payload["message"],
                    context={"request": request},
                ).data,
                "created": bool(payload["created"]),
            },
            status=status.HTTP_201_CREATED,
        )


class OrganizationDirectParticipantReadView(APIView):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def post(self, request, organization_slug):
        organization = _organization(organization_slug)
        context = get_organization_direct_context(
            organization=organization,
            participant_user=request.user,
        )
        if context is None:
            return Response(
                {"error": "Conversation not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = mark_dialogue_read_for_user(
            context.dialogue.slug,
            request.user,
        )
        if not result.get("ok"):
            return _service_error(result)
        return Response(result["payload"], status=status.HTTP_200_OK)


class OrganizationDirectInboxView(APIView):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def get(self, request, organization_slug):
        organization = _organization(organization_slug)
        if not organization_operator_can_view(
            user=request.user,
            organization=organization,
        ):
            return _operator_forbidden()

        queryset = build_organization_direct_inbox_queryset(
            organization=organization,
            operator_user=request.user,
            status_filter=request.query_params.get("status", "open"),
            assignment_filter=request.query_params.get("assigned", "all"),
            unread_only=str(
                request.query_params.get("unread", "")
            ).strip().lower() in {"1", "true", "yes"},
        )

        paginator = OrganizationMessengerPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = OrganizationDirectThreadSerializer(
            page,
            many=True,
            context={"request": request},
        )
        return paginator.get_paginated_response(serializer.data)


class OrganizationDirectInboxUnreadCountView(APIView):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def get(self, request, organization_slug):
        organization = _organization(organization_slug)
        if not organization_operator_can_view(
            user=request.user,
            organization=organization,
        ):
            return _operator_forbidden()

        return Response(
            {
                "unread_count": organization_direct_total_unread_count(
                    organization=organization,
                    operator_user=request.user,
                )
            },
            status=status.HTTP_200_OK,
        )


class OrganizationDirectOperatorConversationView(APIView):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def get(self, request, organization_slug, dialogue_slug):
        organization = _organization(organization_slug)
        if not organization_operator_can_view(
            user=request.user,
            organization=organization,
        ):
            return _operator_forbidden()

        context = get_organization_direct_context_by_slug(
            organization=organization,
            dialogue_slug=dialogue_slug,
        )
        if context is None:
            return Response(
                {"error": "Conversation not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        access = ConversationAccessPolicy.can_view(
            dialogue=context.dialogue,
            user=request.user,
        )
        if not access.allowed:
            return Response(
                {"error": access.message, "code": access.code},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            offset = max(int(request.query_params.get("offset", 0)), 0)
            limit = min(max(int(request.query_params.get("limit", 30)), 1), 100)
        except (TypeError, ValueError):
            offset, limit = 0, 30

        messages_query = (
            context.dialogue
            .visible_messages_for_user(request.user)
            .select_related(
                "sender",
                "organization_attribution__organization",
                "organization_attribution__actor_membership",
                "reply_to__sender",
            )
            .prefetch_related(
                "seen_by_users",
                "encryptions",
                "pins",
            )
            .order_by("-timestamp", "-id")
        )
        total = messages_query.count()
        messages = messages_query[offset:offset + limit]

        return Response(
            {
                "thread": OrganizationDirectThreadSerializer(
                    context,
                    context={"request": request},
                ).data,
                "messages": MessageSerializer(
                    messages,
                    many=True,
                    context={
                        "request": request,
                        "organization_operator_view": True,
                    },
                ).data,
                "has_more": offset + limit < total,
            },
            status=status.HTTP_200_OK,
        )


class OrganizationDirectOperatorReplyView(APIView):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def post(self, request, organization_slug, dialogue_slug):
        organization = _organization(organization_slug)
        context = get_organization_direct_context_by_slug(
            organization=organization,
            dialogue_slug=dialogue_slug,
        )
        if context is None:
            return Response(
                {"error": "Conversation not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = send_organization_direct_reply(
            context=context,
            acting_user=request.user,
            content=request.data.get("content"),
            reply_to_message_id=request.data.get("reply_to_message_id"),
        )
        if not result.get("ok"):
            return _service_error(result)

        payload = result["payload"]
        return Response(
            {
                "thread": OrganizationDirectThreadSerializer(
                    payload["context"],
                    context={"request": request},
                ).data,
                "message": MessageSerializer(
                    payload["message"],
                    context={
                        "request": request,
                        "organization_operator_view": True,
                    },
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class OrganizationDirectOperatorReadView(APIView):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def post(self, request, organization_slug, dialogue_slug):
        organization = _organization(organization_slug)
        context = get_organization_direct_context_by_slug(
            organization=organization,
            dialogue_slug=dialogue_slug,
        )
        if context is None:
            return Response(
                {"error": "Conversation not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = mark_organization_direct_read_for_operator(
            context=context,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return _service_error(result)
        return Response(result["payload"], status=status.HTTP_200_OK)


class OrganizationDirectOperatorAssignView(APIView):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def post(self, request, organization_slug, dialogue_slug):
        organization = _organization(organization_slug)
        context = get_organization_direct_context_by_slug(
            organization=organization,
            dialogue_slug=dialogue_slug,
        )
        if context is None:
            return Response(
                {"error": "Conversation not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        membership_public_id = request.data.get("membership_public_id")
        target_membership = None
        if membership_public_id:
            target_membership = get_object_or_404(
                OrganizationMembership.objects.select_related(
                    "organization",
                    "member__user",
                ),
                public_id=membership_public_id,
                organization=organization,
            )

        result = assign_organization_direct_thread(
            context=context,
            acting_user=request.user,
            target_membership=target_membership,
        )
        if not result.get("ok"):
            return _service_error(result)

        return Response(
            OrganizationDirectThreadSerializer(
                result["payload"]["context"],
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


class OrganizationDirectOperatorLifecycleView(APIView):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]
    target_status = None

    def post(self, request, organization_slug, dialogue_slug):
        organization = _organization(organization_slug)
        context = get_organization_direct_context_by_slug(
            organization=organization,
            dialogue_slug=dialogue_slug,
        )
        if context is None:
            return Response(
                {"error": "Conversation not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = transition_organization_direct_thread(
            context=context,
            acting_user=request.user,
            target_status=self.target_status,
        )
        if not result.get("ok"):
            return _service_error(result)

        return Response(
            OrganizationDirectThreadSerializer(
                result["payload"]["context"],
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


RESOLVE_VIEW = OrganizationDirectOperatorLifecycleView.as_view(
    target_status=OrganizationConversationStatus.RESOLVED,
)
REOPEN_VIEW = OrganizationDirectOperatorLifecycleView.as_view(
    target_status=OrganizationConversationStatus.OPEN,
)
CLOSE_VIEW = OrganizationDirectOperatorLifecycleView.as_view(
    target_status=OrganizationConversationStatus.CLOSED,
)

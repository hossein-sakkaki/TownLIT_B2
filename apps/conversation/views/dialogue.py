# apps/conversation/views/dialogue.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-16.
#

from django.db.models import (
    Case,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conversation.constants import OrganizationConversationContextType
from apps.conversation.models import Dialogue, DialogueParticipant, DialoguePin, Message
from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationContextKind,
    ConversationContextPolicy,
)
from apps.conversation.serializers import DialogueSerializer
from apps.organizations.selectors.ownership import (
    effective_organization_manager_memberships_queryset,
)

from .mixins.dialogue_group_membership import DialogueGroupMembershipActionsMixin
from .mixins.dialogue_group_metadata import DialogueGroupMetadataActionsMixin
from .mixins.dialogue_group_roles import DialogueGroupRoleActionsMixin
from .mixins.dialogue_lifecycle import DialogueLifecycleActionsMixin
from .mixins.dialogue_pins import DialoguePinActionsMixin
from .mixins.dialogue_session import DialogueSessionActionsMixin


class DialogueViewSet(
    DialogueSessionActionsMixin,
    DialogueGroupMetadataActionsMixin,
    DialogueGroupMembershipActionsMixin,
    DialogueGroupRoleActionsMixin,
    DialogueLifecycleActionsMixin,
    DialoguePinActionsMixin,
    viewsets.ModelViewSet,
):
    queryset = Dialogue.objects.all()
    serializer_class = DialogueSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"

    @staticmethod
    def _is_managed_community(dialogue):
        return (
            ConversationContextPolicy.resolve(dialogue).kind
            == ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY
        )

    def update(self, request, *args, **kwargs):
        dialogue = self.get_object()
        if self._is_managed_community(dialogue):
            return Response(
                {
                    "error": (
                        "Members Community structure is managed by "
                        "Organization lifecycle."
                    ),
                    "code": "organization_community_system_managed",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        dialogue = self.get_object()
        if self._is_managed_community(dialogue):
            return Response(
                {
                    "error": (
                        "Members Community cannot be deleted manually."
                    ),
                    "code": "organization_community_system_managed",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def _base_qs(self):
        # Personal behavior remains unchanged. Organization contexts are
        # filtered through the shared access policy before list/retrieve.
        queryset = (
            Dialogue.objects
            .filter(participants=self.request.user)
            .exclude(deleted_by_users=self.request.user)
        )

        organization_dialogues = list(
            queryset
            .filter(organization_context__isnull=False)
            .select_related(
                "organization_context__organization",
            )
        )
        denied_ids = [
            dialogue.id
            for dialogue in organization_dialogues
            if not ConversationAccessPolicy.can_view(
                dialogue=dialogue,
                user=self.request.user,
            ).allowed
        ]
        if denied_ids:
            queryset = queryset.exclude(id__in=denied_ids)

        return queryset

    @staticmethod
    def _organization_manager_memberships_prefetch():
        return Prefetch(
            "organization_context__organization__memberships",
            queryset=(
                effective_organization_manager_memberships_queryset()
                .select_related("member__user")
            ),
            to_attr="_conversation_manager_memberships",
        )

    def _with_last_activity(
        self,
        qs,
    ):
        """
        Order dialogues by:
        1) pinned dialogues first
        2) pinned position ascending
        3) latest visible delivery-ready non-system activity
        4) created_at fallback
        Pending asynchronous Group Messenger video must not reorder
        the dialogue list before Content Safety approval.
        Notes:
        - pin state is per-user
        - activity is visibility-aware per-user
        """
        user = self.request.user
        community_joined_at = Subquery(
            DialogueParticipant.objects
            .filter(
                dialogue_id=OuterRef("dialogue_id"),
                user=user,
            )
            .values("joined_at")[:1]
        )
        visible_last_message_ts = Subquery(
            Message.objects
            .filter(
                dialogue=OuterRef(
                    "pk"
                ),
                is_system=False,
                is_delivery_ready=True,
            )
            .filter(
                Q(dialogue__organization_context__isnull=True)
                | Q(
                    dialogue__organization_context__context_type=(
                        OrganizationConversationContextType.DIRECT
                    )
                )
                | Q(
                    dialogue__organization_context__context_type=(
                        OrganizationConversationContextType.MEMBERS_COMMUNITY
                    ),
                    timestamp__gte=community_joined_at,
                )
            )
            .exclude(
                deleted_by_users=user
            )
            .order_by(
                "-timestamp",
                "-id",
            )
            .values(
                "timestamp"
            )[:1]
        )
        pinned_position_subquery = Subquery(
            DialoguePin.objects
            .filter(
                user=user,
                dialogue=OuterRef(
                    "pk"
                ),
            )
            .values(
                "position"
            )[:1],
            output_field=IntegerField(),
        )
        return (
            qs.select_related(
                "organization_context__organization",
            )
            .annotate(
                last_msg_ts=(
                    visible_last_message_ts
                ),
                last_activity=Coalesce(
                    "last_msg_ts",
                    "created_at",
                ),
                pinned_position=(
                    pinned_position_subquery
                ),
                is_pinned_sort=Case(
                    When(
                        pinned_position__isnull=False,
                        then=Value(
                            1
                        ),
                    ),
                    default=Value(
                        0
                    ),
                    output_field=IntegerField(),
                ),
            )
            .order_by(
                "-is_pinned_sort",
                "pinned_position",
                "-last_activity",
                "-created_at",
            )
            .prefetch_related(
                "participants",
                "participants_roles",
                "marked_users",
                self._organization_manager_memberships_prefetch(),
            )
        )

    def get_queryset(self):
        # used by default list/retrieve
        base = self._base_qs()
        return self._with_last_activity(base)

    def _serialize_single_dialogue(self, request, dialogue, device_id=None):
        """
        Serialize one dialogue with the same annotated ordering fields.
        """
        hydrated = self._with_last_activity(
            Dialogue.objects.filter(pk=dialogue.pk)
        ).first()
        serializer = DialogueSerializer(
            hydrated or dialogue,
            context={"request": request, "device_id": device_id},
        )
        return serializer.data

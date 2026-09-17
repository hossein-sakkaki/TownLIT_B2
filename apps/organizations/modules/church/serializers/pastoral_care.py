# apps/organizations/modules/church/serializers/pastoral_care.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.organizations.modules.church.constants import (
    ChurchPastoralCareAssignmentRole,
    ChurchPastoralCareAssignmentStatus,
    ChurchPastoralCareCaseStatus,
    ChurchPastoralCareCategory,
    ChurchPastoralCareContactType,
    ChurchPastoralCareNoteType,
    ChurchPastoralCareNoteVisibility,
    ChurchPastoralCareSensitivity,
)
from apps.organizations.modules.church.models import (
    ChurchCongregant,
    ChurchPastoralCareAssignment,
    ChurchPastoralCareCase,
    ChurchPastoralCareContact,
    ChurchPastoralCareNote,
)
from apps.organizations.modules.church.selectors.congregation import (
    get_church_congregant_display_name,
)
from apps.organizations.modules.church.services.pastoral_care import (
    get_pastoral_care_case_closure_summary,
    get_pastoral_care_case_summary,
    get_pastoral_care_contact_summary,
    get_pastoral_care_note_body,
)


class ChurchPastoralCongregantSerializer(serializers.ModelSerializer):
    identity_kind = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    campus_public_id = serializers.UUIDField(
        source="campus.public_id",
        read_only=True,
        allow_null=True,
    )
    campus_name = serializers.CharField(
        source="campus.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ChurchCongregant
        fields = [
            "public_id",
            "identity_kind",
            "display_name",
            "user",
            "status",
            "campus_public_id",
            "campus_name",
            "is_active",
        ]
        read_only_fields = fields

    def get_identity_kind(self, obj):
        if obj.member_id:
            return "member"
        if obj.guest_profile_id:
            return "guest"
        return "external"

    def get_display_name(self, obj):
        return get_church_congregant_display_name(obj)

    def get_user(self, obj):
        user = None
        if obj.member_id:
            user = obj.member.user
        elif obj.guest_profile_id:
            user = obj.guest_profile.user

        if user is None:
            return None

        return UserMiniSerializer(
            user,
            context=self.context,
        ).data


class ChurchPastoralCareAssignmentSerializer(serializers.ModelSerializer):
    membership_public_id = serializers.UUIDField(
        source="membership.public_id",
        read_only=True,
        allow_null=True,
    )
    user = serializers.SerializerMethodField()

    class Meta:
        model = ChurchPastoralCareAssignment
        fields = [
            "public_id",
            "membership_public_id",
            "user",
            "role",
            "status",
            "assigned_at",
            "ended_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_user(self, obj):
        if not obj.membership_id:
            return None
        return UserMiniSerializer(
            obj.membership.member.user,
            context=self.context,
        ).data


class ChurchPastoralCareCaseListSerializer(serializers.ModelSerializer):
    congregant = ChurchPastoralCongregantSerializer(read_only=True)

    class Meta:
        model = ChurchPastoralCareCase
        fields = [
            "public_id",
            "congregant",
            "category",
            "sensitivity",
            "status",
            "title",
            "opened_at",
            "closed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchPastoralCareCaseSerializer(serializers.ModelSerializer):
    congregant = ChurchPastoralCongregantSerializer(read_only=True)
    summary = serializers.SerializerMethodField()
    closure_summary = serializers.SerializerMethodField()
    opened_by_membership_public_id = serializers.UUIDField(
        source="opened_by_membership.public_id",
        read_only=True,
        allow_null=True,
    )
    closed_by_membership_public_id = serializers.UUIDField(
        source="closed_by_membership.public_id",
        read_only=True,
        allow_null=True,
    )
    assignments = ChurchPastoralCareAssignmentSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = ChurchPastoralCareCase
        fields = [
            "public_id",
            "congregant",
            "category",
            "sensitivity",
            "status",
            "title",
            "summary",
            "closure_summary",
            "opened_by_membership_public_id",
            "closed_by_membership_public_id",
            "opened_at",
            "closed_at",
            "assignments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _actor(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_summary(self, obj):
        return get_pastoral_care_case_summary(
            care_case=obj,
            actor=self._actor(),
        )

    def get_closure_summary(self, obj):
        if not obj.closed_at:
            return ""
        return get_pastoral_care_case_closure_summary(
            care_case=obj,
            actor=self._actor(),
        )


class ChurchPastoralCareNoteSerializer(serializers.ModelSerializer):
    author_membership_public_id = serializers.UUIDField(
        source="author_membership.public_id",
        read_only=True,
        allow_null=True,
    )
    author_user = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    amends_note_public_id = serializers.UUIDField(
        source="amends_note.public_id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ChurchPastoralCareNote
        fields = [
            "public_id",
            "author_membership_public_id",
            "author_user",
            "note_type",
            "visibility",
            "body",
            "amends_note_public_id",
            "created_at",
        ]
        read_only_fields = fields

    def _actor(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_author_user(self, obj):
        if not obj.author_membership_id:
            return None
        return UserMiniSerializer(
            obj.author_membership.member.user,
            context=self.context,
        ).data

    def get_body(self, obj):
        return get_pastoral_care_note_body(
            note=obj,
            actor=self._actor(),
        )


class ChurchPastoralCareContactSerializer(serializers.ModelSerializer):
    actor_membership_public_id = serializers.UUIDField(
        source="actor_membership.public_id",
        read_only=True,
        allow_null=True,
    )
    actor_user = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = ChurchPastoralCareContact
        fields = [
            "public_id",
            "actor_membership_public_id",
            "actor_user",
            "contact_type",
            "occurred_at",
            "summary",
            "follow_up_required",
            "follow_up_due_at",
            "created_at",
        ]
        read_only_fields = fields

    def _actor(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_actor_user(self, obj):
        if not obj.actor_membership_id:
            return None
        return UserMiniSerializer(
            obj.actor_membership.member.user,
            context=self.context,
        ).data

    def get_summary(self, obj):
        return get_pastoral_care_contact_summary(
            contact=obj,
            actor=self._actor(),
        )


class ChurchPastoralCareCaseCreateSerializer(serializers.Serializer):
    congregant_public_id = serializers.UUIDField()
    title = serializers.CharField(max_length=180)
    category = serializers.ChoiceField(
        choices=ChurchPastoralCareCategory.choices,
        default=ChurchPastoralCareCategory.GENERAL,
    )
    sensitivity = serializers.ChoiceField(
        choices=ChurchPastoralCareSensitivity.choices,
        default=ChurchPastoralCareSensitivity.STANDARD,
    )
    summary = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=20000,
        default="",
    )


class ChurchPastoralCareAssignmentCreateSerializer(serializers.Serializer):
    membership_public_id = serializers.UUIDField()
    role = serializers.ChoiceField(
        choices=ChurchPastoralCareAssignmentRole.choices,
        default=ChurchPastoralCareAssignmentRole.SUPPORT,
    )


class ChurchPastoralCareNoteCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=20000)
    note_type = serializers.ChoiceField(
        choices=ChurchPastoralCareNoteType.choices,
        default=ChurchPastoralCareNoteType.GENERAL,
    )
    visibility = serializers.ChoiceField(
        choices=ChurchPastoralCareNoteVisibility.choices,
        default=ChurchPastoralCareNoteVisibility.CASE_TEAM,
    )
    amends_note_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )


class ChurchPastoralCareContactCreateSerializer(serializers.Serializer):
    contact_type = serializers.ChoiceField(
        choices=ChurchPastoralCareContactType.choices,
    )
    occurred_at = serializers.DateTimeField(required=False)
    summary = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=20000,
        default="",
    )
    follow_up_required = serializers.BooleanField(default=False)
    follow_up_due_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )


class ChurchPastoralCareCloseSerializer(serializers.Serializer):
    closure_summary = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=20000,
        default="",
    )


class ChurchPastoralCareReferenceSerializer(serializers.Serializer):
    case_statuses = serializers.ListField(child=serializers.DictField())
    categories = serializers.ListField(child=serializers.DictField())
    sensitivities = serializers.ListField(child=serializers.DictField())
    assignment_roles = serializers.ListField(child=serializers.DictField())
    assignment_statuses = serializers.ListField(child=serializers.DictField())
    note_types = serializers.ListField(child=serializers.DictField())
    note_visibilities = serializers.ListField(child=serializers.DictField())
    contact_types = serializers.ListField(child=serializers.DictField())

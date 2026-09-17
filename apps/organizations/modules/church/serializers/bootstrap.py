# apps/organizations/modules/church/serializers/bootstrap.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from rest_framework import serializers

from .gatherings import ChurchGatheringOccurrenceSerializer
from .workspace import (
    ChurchCampusSerializer,
    ChurchLeadershipAssignmentSerializer,
    ChurchMinistrySerializer,
    ChurchWorkspaceSerializer,
)


class ChurchModuleAccessSerializer(serializers.Serializer):
    access_mode = serializers.CharField()
    reason = serializers.CharField()
    is_verified = serializers.BooleanField()
    has_entitlement = serializers.BooleanField()
    can_manage_module = serializers.BooleanField()
    domain_writable = serializers.BooleanField()


class ChurchBootstrapSerializer(serializers.Serializer):
    contract_version = serializers.IntegerField()
    workspace = ChurchWorkspaceSerializer()
    access = ChurchModuleAccessSerializer()
    permissions = serializers.DictField(
        child=serializers.BooleanField(),
    )
    campuses = ChurchCampusSerializer(many=True)
    ministries = ChurchMinistrySerializer(many=True)
    leadership = ChurchLeadershipAssignmentSerializer(many=True)
    upcoming_gatherings = ChurchGatheringOccurrenceSerializer(many=True)

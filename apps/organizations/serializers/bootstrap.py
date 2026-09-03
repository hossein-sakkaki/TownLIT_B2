# apps/organizations/serializers/bootstrap.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from rest_framework import serializers


class OrganizationCreationEligibilitySerializer(serializers.Serializer):
    eligible = serializers.BooleanField()
    code = serializers.CharField()
    detail = serializers.CharField()


class OrganizationClientFeatureFlagsSerializer(serializers.Serializer):
    ios = serializers.BooleanField()
    android = serializers.BooleanField()
    web_admin = serializers.BooleanField()


class OrganizationFeatureFlagsSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    creation = serializers.BooleanField()
    verification = serializers.BooleanField()
    hierarchy = serializers.BooleanField()
    governance = serializers.BooleanField()
    modules = serializers.BooleanField()
    clients = OrganizationClientFeatureFlagsSerializer()

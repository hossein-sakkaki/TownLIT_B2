from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.profiles.models.client import ClientRequest, Client
from apps.profilesOrg.serializers_min import SimpleOrganizationSerializer

CustomUser = get_user_model()


class ClientRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientRequest
        fields = [
            "id",
            "request",
            "description",
            "document_1",
            "document_2",
            "register_date",
            "is_active",
        ]
        read_only_fields = ["register_date"]

    def validate_document_1(self, value):
        if value and value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("The document size exceeds the limit of 2MB.")
        valid_file_types = ["application/pdf", "image/jpeg", "image/png"]
        if value and value.content_type not in valid_file_types:
            raise serializers.ValidationError("Only PDF, JPEG, and PNG files are allowed.")
        return value

    def validate_document_2(self, value):
        if value and value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("The document size exceeds the limit of 2MB.")
        valid_file_types = ["application/pdf", "image/jpeg", "image/png"]
        if value and value.content_type not in valid_file_types:
            raise serializers.ValidationError("Only PDF, JPEG, and PNG files are allowed.")
        return value

    def validate(self, data):
        if not data.get("document_1") and not data.get("document_2"):
            raise serializers.ValidationError("At least one document should be uploaded.")
        return data


class ClientSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())
    request = ClientRequestSerializer(read_only=True)

    class Meta:
        model = Client
        fields = ["user", "organization_clients", "request", "register_date", "is_active", "slug"]
        read_only_fields = ["register_date", "slug"]

    def get_fields(self):
        fields = super().get_fields()
        fields["organization_clients"] = SimpleOrganizationSerializer(many=True, read_only=True)
        return fields

    def validate(self, data):
        if data.get("is_active") and not data.get("request"):
            raise serializers.ValidationError("Active client must have a request.")
        return data
# apps/profiles/serializers/services.py

from django.http import QueryDict
from rest_framework import serializers

from apps.profiles.helpers.text import humanize_service_code
from apps.profiles.models.services import MemberServiceType, SpiritualService
from apps.profiles.constants.ministry import STANDARD_MINISTRY_CHOICES
from validators.files_validator import validate_http_https
from common.file_handlers.document_file import DocumentFileMixin


# Spiritual Service Serializer ----------------------------------------------
class SpiritualServiceSerializer(serializers.ModelSerializer):
    # short, stable display label for UI
    name_display = serializers.SerializerMethodField()

    class Meta:
        model = SpiritualService
        fields = ["id", "name", "name_display", "is_sensitive"]  # add other fields as needed

    def get_name_display(self, obj):
        """
        Prefer model choices display; else map from constant; else humanize fallback.
        """
        # 1) If model field has choices -> use get_FOO_display()
        if hasattr(obj, "get_name_display"):
            try:
                disp = obj.get_name_display()
                if disp:
                    return str(disp)
            except Exception:
                pass

        # 2) Map by constant list (safe for i18n)
        try:
            mapping = dict(STANDARD_MINISTRY_CHOICES)
            label = mapping.get(getattr(obj, "name", None))
            if label:
                return str(label)
        except Exception:
            pass

        # 3) Fallback: Title-case + keep acronyms upper-case
        return humanize_service_code(getattr(obj, "name", "") or "") 


# Member Service Type Serializer --------------------------------------------
class MemberServiceTypeSerializer(DocumentFileMixin, serializers.ModelSerializer):
    service = SpiritualServiceSerializer(read_only=True)
    service_id = serializers.PrimaryKeyRelatedField(
        queryset=SpiritualService.objects.filter(is_active=True),
        source="service",
        write_only=True,
        required=True,
    )

    remove_document = serializers.BooleanField(write_only=True, required=False, default=False)

    # optional: expose status & review_note to client
    status = serializers.CharField(read_only=True)
    review_note = serializers.CharField(read_only=True)

    # inputs
    history = serializers.CharField(required=False, allow_blank=True, max_length=500)
    credential_issuer = serializers.CharField(required=False, allow_blank=True, max_length=120)
    credential_number = serializers.CharField(required=False, allow_blank=True, max_length=80)
    credential_url = serializers.URLField(required=False, allow_blank=True, validators=[validate_http_https])
    issued_at = serializers.DateField(required=False, allow_null=True)
    expires_at = serializers.DateField(required=False, allow_null=True)

    signed_fields = { "document": None }  # adds document_key & document_url

    class Meta:
        model = MemberServiceType
        fields = [
            "id",
            "service", "service_id",
            "history", "document", "register_date",
            "status", "review_note",
            "is_active",
            "credential_issuer", "credential_number", "credential_url",
            "issued_at", "expires_at", "verified_at", "reviewed_at", "reviewed_by",
            "remove_document",
        ]
        read_only_fields = [
            "id", "is_active", "register_date",
            "status", "review_note", "verified_at", "reviewed_at", "reviewed_by",
        ]

    # -------- normalize inputs --------
    def to_internal_value(self, data):
        # Make a mutable copy; QueryDict is immutable by default
        if isinstance(data, QueryDict):
            data = data.copy()

        # Trim simple string fields (no list handling needed here)
        for f in ["history", "credential_issuer", "credential_number", "credential_url"]:
            val = data.get(f, None)
            if isinstance(val, str):
                data[f] = val.strip()

        # Normalize empty dates -> None (let DRF parse None)
        for df in ["issued_at", "expires_at"]:
            val = data.get(df, None)
            if val in ("", None):
                data[df] = None

        # Hand off to DRF for standard parsing/validation
        return super().to_internal_value(data)

    # -------- validate --------
    def validate(self, attrs):
        self._remove_document_flag = bool(attrs.pop("remove_document", False))

        service = attrs.get("service") or getattr(self.instance, "service", None)
        incoming_doc = attrs.get("document", serializers.empty)
        current_doc  = getattr(self.instance, "document", None) if self.instance else None

        # lock when approved (non-admin users)
        request = self.context.get("request")
        is_admin = bool(request and request.user and request.user.is_staff)
        current_status = getattr(self.instance, "status", None)

        # deny file remove/replace on approved for non-admins
        if self.instance and current_status == MemberServiceType.Status.APPROVED and not is_admin:
            if self._remove_document_flag or incoming_doc is not serializers.empty:
                raise serializers.ValidationError({
                    "document": "This service is approved. You cannot change or remove its document."
                })

        # effective doc for policy check
        if self._remove_document_flag:
            effective_doc = None
        elif incoming_doc is not serializers.empty:
            effective_doc = incoming_doc
        else:
            effective_doc = current_doc

        issuer     = attrs.get("credential_issuer") or getattr(self.instance, "credential_issuer", None)
        issued_at  = attrs.get("issued_at") or getattr(self.instance, "issued_at", None)
        expires_at = attrs.get("expires_at") or getattr(self.instance, "expires_at", None)

        if service and getattr(service, "is_sensitive", False):
            has_doc = bool(effective_doc)
            has_endorsement = bool(issuer) and bool(issued_at)
            if not (has_doc or has_endorsement):
                raise serializers.ValidationError({
                    "document": "Provide a PDF credential or issuer & issued date for this sensitive service."
                })

        if issued_at and expires_at and expires_at < issued_at:
            raise serializers.ValidationError({"expires_at": "Expiration date cannot be before issue date."})

        return attrs

    # -------- create --------
    def create(self, validated_data):
        # set initial status based on service sensitivity
        service = validated_data["service"]
        if service.is_sensitive:
            validated_data["status"] = MemberServiceType.Status.PENDING
        else:
            validated_data["status"] = MemberServiceType.Status.ACTIVE

        # ensure not leaking temp flag
        validated_data.pop("_remove_document_flag", None)
        return super().create(validated_data)

    # -------- update --------
    def update(self, instance, validated_data):
        # forbid changing service
        if "service" in validated_data and validated_data["service"] != instance.service:
            raise serializers.ValidationError({"service_id": "Changing service is not allowed."})

        remove_flag = getattr(self, "_remove_document_flag", False)
        new_file = validated_data.get("document", serializers.empty)

        # --- file handling (unchanged) ---
        if remove_flag and new_file is serializers.empty:
            if instance.document:
                instance.document.delete(save=False)
            instance.document = None
        elif remove_flag and new_file is not serializers.empty:
            if instance.document:
                instance.document.delete(save=False)
            # keep new file in validated_data
        elif new_file is not serializers.empty and instance.document:
            instance.document.delete(save=False)

        # --- detect meaningful content changes ---
        tracked_fields = (
            "document", "credential_issuer", "credential_number", "credential_url",
            "issued_at", "expires_at", "history",
        )
        content_changed = any(f in validated_data for f in tracked_fields) or remove_flag

        try:
            from apps.profiles.models import MemberServiceType
            was_final = instance.status in {MemberServiceType.Status.APPROVED, MemberServiceType.Status.REJECTED}
            if was_final and content_changed:
                validated_data["status"] = MemberServiceType.Status.PENDING
                # DO NOT clear review_note / reviewed_at / reviewed_by / verified_at
        except Exception:
            pass

        return super().update(instance, validated_data)



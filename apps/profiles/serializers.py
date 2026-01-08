from rest_framework import serializers
from django.apps import apps
from django.http import QueryDict
from django.db.models import Q
from django.utils import timezone 
from django.core.validators import RegexValidator
from django.db.models.functions import Lower
from .models import (
                Friendship, Fellowship, MemberServiceType,AcademicRecord, StudyStatus,
                Member, GuestUser,
                ClientRequest, Client, Customer, MigrationHistory,
                SpiritualGift, SpiritualGiftSurveyQuestion, SpiritualGiftSurveyResponse, MemberSpiritualGifts,
                SpiritualService
            )
from .helpers import (
    testimonies_for_member,
    social_links_for_user,
    fellowships_visible,
    randomized_friends_for_member,
    journey_weights_for,
    friends_queryset_for,
    humanize_service_code,
)
from apps.profilesOrg.serializers_min import SimpleOrganizationSerializer
from apps.accounts.models import SocialMediaLink
from apps.core.ownership.utils import resolve_owner_from_request
from validators.files_validator import validate_http_https, soft_date_bounds
from apps.accounts.serializers import (
                                AddressSerializer, SimpleCustomUserSerializer,
                                CustomUserSerializer, PublicCustomUserSerializer, LimitedCustomUserSerializer, 
                                SocialMediaLinkReadOnlySerializer
                            )
from common.file_handlers.document_file import DocumentFileMixin
from apps.posts.services.feed_access import get_visible_posts
from apps.posts.models.testimony import Testimony
from apps.posts.serializers.testimonies import TestimonySerializer
from apps.profilesOrg.constants_denominations import CHURCH_BRANCH_CHOICES, CHURCH_FAMILY_CHOICES_ALL, FAMILIES_BY_BRANCH
from apps.profiles.constants import FRIENDSHIP_STATUS_CHOICES, FELLOWSHIP_RELATIONSHIP_CHOICES, RECIPROCAL_FELLOWSHIP_CHOICES, RECIPROCAL_FELLOWSHIP_MAP, STANDARD_MINISTRY_CHOICES
from django.contrib.auth import get_user_model
import logging
logger = logging.getLogger(__name__)
CustomUser = get_user_model()


# FRIENDSHIP Serializer ---------------------------------------------------------------
class FriendshipSerializer(serializers.ModelSerializer):
    from_user = SimpleCustomUserSerializer(read_only=True)
    to_user = SimpleCustomUserSerializer(read_only=True)
    to_user_id = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all(), write_only=True)

    class Meta:
        model = Friendship
        fields = ['id', 'from_user', 'to_user', 'to_user_id', 'created_at', 'status', 'deleted_at', 'is_active']
        read_only_fields = ['from_user', 'to_user', 'created_at', 'deleted_at']

    def validate_to_user_id(self, value):
        # Ensures that a user cannot send a friend request to themselves
        if self.context['request'].user == value:
            raise serializers.ValidationError("You cannot send a friend request to yourself.")
        return value

    def validate_status(self, value):
        # Checks if the status is valid
        valid_statuses = [choice[0] for choice in FRIENDSHIP_STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError("Invalid status for friendship.")
        return value

    def create(self, validated_data):
        from_user = self.context['request'].user
        to_user = validated_data.pop('to_user_id')

        # Check for existing active requests
        existing_request = Friendship.objects.filter(
            from_user=from_user,
            to_user=to_user,
            is_active=True
        ).exclude(status='declined')

        if existing_request.exists():
            raise serializers.ValidationError("Friendship request already exists.")

        validated_data.pop('from_user', None)
        validated_data.pop('to_user', None)
        return Friendship.objects.create(
            from_user=from_user,
            to_user=to_user,
            **validated_data
        )

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # hard guard: if any side is deleted, suppress this record
        try:
            if instance.from_user.is_deleted or instance.to_user.is_deleted:
                return None
        except Exception:
            pass
        return rep

# FELLOWSHIP Serializer ---------------------------------------------------------------
class FellowshipSerializer(serializers.ModelSerializer):
    from_user = SimpleCustomUserSerializer(read_only=True)
    to_user = SimpleCustomUserSerializer(read_only=True)
    to_user_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(is_deleted=False, is_active=True),
        write_only=True
    )    
    reciprocal_fellowship_type = serializers.CharField(required=False)

    class Meta:
        model = Fellowship
        fields = [
            'id', 'from_user', 'to_user', 'to_user_id', 'fellowship_type', 'reciprocal_fellowship_type', 'status', 'created_at',
        ]
        read_only_fields = ['from_user', 'to_user', 'created_at', 'reciprocal_fellowship_type']

    def validate_to_user_id(self, value):
        if self.context['request'].user == value:
            raise serializers.ValidationError("You cannot send a request to yourself.")
        return value

    def validate_fellowship_type(self, value):
        valid_types = [choice[0] for choice in FELLOWSHIP_RELATIONSHIP_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError("Invalid fellowship type.")
        return value

    def validate_reciprocal_fellowship_type(self, value):
        if value:
            valid_types = [choice[0] for choice in RECIPROCAL_FELLOWSHIP_CHOICES]
            if value not in valid_types:
                raise serializers.ValidationError("Invalid reciprocal fellowship type.")
        return value

    def validate(self, data):
        from_user = self.context['request'].user
        to_user = data.get('to_user_id')
        fellowship_type = data.get('fellowship_type')
        reciprocal_fellowship_type = RECIPROCAL_FELLOWSHIP_MAP.get(fellowship_type)

        # self-checks
        if from_user == to_user:
            raise serializers.ValidationError({"error": "You cannot send a fellowship request to yourself."})

        # ⛔️ deleted guards
        if getattr(from_user, "is_deleted", False):
            raise serializers.ValidationError({"error": "Your account is deactivated. Reactivate to manage fellowships."})
        if getattr(to_user, "is_deleted", False):
            raise serializers.ValidationError({"error": "You cannot send a fellowship request to a deactivated account."})

        # پایه‌ی کوئری: فقط لبه‌هایی که هیچ‌کدام حذف‌شده نیستند
        base_qs = Fellowship.objects.filter(from_user__is_deleted=False, to_user__is_deleted=False)

        existing_fellowship = base_qs.filter(
            Q(from_user=from_user, to_user=to_user, fellowship_type=fellowship_type, status='Accepted') |
            Q(from_user=to_user, to_user=from_user, fellowship_type=reciprocal_fellowship_type, status='Accepted')
        ).exists()
        if existing_fellowship:
            raise serializers.ValidationError({
                "error": f"A fellowship of type '{fellowship_type}' or its reciprocal already exists."
            })

        existing_reciprocal_fellowship = base_qs.filter(
            Q(from_user=from_user, to_user=to_user, fellowship_type=reciprocal_fellowship_type, status='Accepted') |
            Q(from_user=to_user, to_user=from_user, fellowship_type=fellowship_type, status='Accepted')
        ).exists()
        if existing_reciprocal_fellowship:
            raise serializers.ValidationError({
                "error": f"A reciprocal fellowship of type '{reciprocal_fellowship_type}' already exists."
            })

        duplicate_fellowship = base_qs.filter(
            from_user=from_user,
            to_user=to_user,
            fellowship_type=fellowship_type,
            status='Pending'
        ).exists()
        if duplicate_fellowship:
            raise serializers.ValidationError({
                "error": f"A pending fellowship request as '{fellowship_type}' already exists."
            })

        reciprocal_pending_fellowship = base_qs.filter(
            Q(from_user=from_user, to_user=to_user, status='Pending') |
            Q(from_user=to_user, to_user=from_user, status='Pending'),
            fellowship_type=reciprocal_fellowship_type
        ).exists()
        if reciprocal_pending_fellowship:
            raise serializers.ValidationError({
                "error": f"You cannot send a fellowship request as '{fellowship_type}' because a pending request already exists as '{reciprocal_fellowship_type}'."
            })

        return data

    def create(self, validated_data):
        to_user = validated_data.pop('to_user_id')
        if getattr(to_user, "is_deleted", False):
            raise serializers.ValidationError("Cannot create fellowship with a deactivated account.")

        reciprocal_fellowship_type = validated_data.pop('reciprocal_fellowship_type', None)
        return Fellowship.objects.create(
            to_user=to_user,
            reciprocal_fellowship_type=reciprocal_fellowship_type,
            **validated_data
        )

    def to_representation(self, instance):
        if getattr(instance.from_user, "is_deleted", False) or getattr(instance.to_user, "is_deleted", False):
            return None
        return super().to_representation(instance)


# ACADEMIC RECORD Serializer --------------------------------------------------------------------------------
class YearMonthDateField(serializers.DateField):
    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m", input_formats=["%Y-%m", "%Y-%m-%d"], **kwargs)

    def to_internal_value(self, value):
        date = super().to_internal_value(value)
        # force day=1 to keep month-level precision
        return date.replace(day=1)

class AcademicRecordSerializer(serializers.ModelSerializer):
    started_at = YearMonthDateField(required=False, allow_null=True)
    expected_graduation_at = YearMonthDateField(required=False, allow_null=True)
    graduated_at = YearMonthDateField(required=False, allow_null=True)
    period_display = serializers.ReadOnlyField()

    class Meta:
        model = AcademicRecord
        fields = [
            'id',
            'education_document_type', 'education_degree', 'school', 'country',
            'status',
            'started_at', 'expected_graduation_at', 'graduated_at',
            'document',
            'is_theology_related',
            'is_approved', 'is_active',
            'period_display',
        ]
        read_only_fields = ['document', 'period_display']



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

        # اگر قبلاً approved/rejected بوده و تغییری رخ داده → فقط status را pending کن
        # نکته: review_note / reviewed_at / reviewed_by را دست نمی‌زنیم تا ادمین بعدی سابقه را ببیند
        try:
            from apps.profiles.models import MemberServiceType
            was_final = instance.status in {MemberServiceType.Status.APPROVED, MemberServiceType.Status.REJECTED}
            if was_final and content_changed:
                validated_data["status"] = MemberServiceType.Status.PENDING
                # DO NOT clear review_note / reviewed_at / reviewed_by / verified_at
        except Exception:
            pass

        return super().update(instance, validated_data)


# -----------------------------------------------------------------------
class FriendsBlockMixin:
    """Reusable friends getter for serializers with Member obj + request in context."""
    def _build_friends_payload(self, member_obj):
        request = self.context.get("request")
        q = getattr(request, "query_params", {}) if request else {}

        random_flag = str(q.get("random", "1")) == "1"
        daily_flag  = str(q.get("daily",  "0")) == "1"
        seed        = q.get("seed")

        try:
            limit = int(q.get("limit")) if q.get("limit") is not None else None
        except (TypeError, ValueError):
            limit = None

        if not random_flag:
            qs = friends_queryset_for(member_obj.user).annotate(
                username_lower=Lower('username')
            ).order_by('username_lower')
            if isinstance(limit, int) and limit > 0:
                qs = qs[:limit]
            return SimpleCustomUserSerializer(qs, many=True, context=self.context).data

        base_ids = list(friends_queryset_for(member_obj.user).values_list("id", flat=True))
        j_weights = journey_weights_for(member_obj.user, base_ids)

        ordered = randomized_friends_for_member(
            member_obj.user,
            daily=daily_flag,
            seed=seed,
            limit=limit,
            journey_weight_map=j_weights,
        )
        return SimpleCustomUserSerializer(ordered, many=True, context=self.context).data

# MEMBER Serializer ------------------------------------------------------------------------------
def _titleize_slug(value: str) -> str:
    # Fallback: "roman_catholicism" -> "Roman Catholicism"
    if not value:
        return value
    return value.replace("_", " ").title()

class MemberSerializer(FriendsBlockMixin, serializers.ModelSerializer):
    user = CustomUserSerializer(context=None)
    service_types = MemberServiceTypeSerializer(many=True, read_only=True)
    academic_record = AcademicRecordSerializer()
    litcovenant = serializers.SerializerMethodField()
    spiritual_gifts = serializers.SerializerMethodField()

    friends = serializers.SerializerMethodField()

    # Editable fields (kept as before)
    denomination_branch = serializers.ChoiceField(choices=CHURCH_BRANCH_CHOICES)
    denomination_family = serializers.ChoiceField(
        choices=CHURCH_FAMILY_CHOICES_ALL, required=False, allow_null=True, allow_blank=False
    )

    # NEW: Read-only display labels for UI
    denomination_branch_label = serializers.SerializerMethodField()
    denomination_family_label = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = [
            'user', 'service_types', 'organization_memberships', 'academic_record',
            'spiritual_rebirth_day', 'biography', 'vision',

            # values (writable)
            'denomination_branch', 'denomination_family',
            # labels (read-only)
            'denomination_branch_label', 'denomination_family_label',

            'show_gifts_in_profile', 'show_fellowship_in_profile', 'hide_confidants', 'is_hidden_by_confidants',
            'register_date', 
            'is_townlit_verified', 'townlit_verified_at',
            'is_privacy', 'is_migrated', 'is_active', 
            'litcovenant', 'spiritual_gifts',
             'friends',
        ]
        read_only_fields = [
            'register_date', 'is_migrated', 'is_active',
            'is_townlit_verified', 'townlit_verified_at',
            'denomination_branch_label', 'denomination_family_label',
        ]

    def get_fields(self):
        # lazy import to avoid circular imports
        fields = super().get_fields()
        from apps.profilesOrg.serializers import OrganizationSerializer
        fields['organization_memberships'] = OrganizationSerializer(many=True, read_only=True)
        return fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # keep context for nested user
        self.fields['user'] = CustomUserSerializer(context=self.context)

    # --- labels for front-end (read-only) ---
    def get_denomination_branch_label(self, obj: Member):
        """Return human display label; fallback to titlecased slug."""
        try:
            # Works because denomination_branch has choices
            label = obj.get_denomination_branch_display()
            return label or _titleize_slug(obj.denomination_branch or "")
        except Exception:
            return _titleize_slug(obj.denomination_branch or "")

    def get_denomination_family_label(self, obj: Member):
        """Return human display label for family (or None); fallback to titlecased slug."""
        if not obj.denomination_family:
            return None
        try:
            label = obj.get_denomination_family_display()
            return label or _titleize_slug(obj.denomination_family)
        except Exception:
            return _titleize_slug(obj.denomination_family)

    # --- update logic (unchanged) ---
    def update(self, instance, validated_data):
        custom_user_data = validated_data.pop('user', None)
        if custom_user_data:
            custom_user_serializer = CustomUserSerializer(instance.user, data=custom_user_data, partial=True)
            if custom_user_serializer.is_valid():
                custom_user_serializer.save()
            else:
                raise serializers.ValidationError({"error": "Custom user update failed. Please check the provided data."})

        academic_record_data = validated_data.pop('academic_record', None)
        if academic_record_data:
            academic_record_instance = instance.academic_record
            if not academic_record_instance:
                academic_record_instance = AcademicRecord.objects.create()
                instance.academic_record = academic_record_instance
                instance.save()

            academic_record_serializer = AcademicRecordSerializer(
                academic_record_instance, data=academic_record_data, partial=True
            )
            if academic_record_serializer.is_valid():
                academic_record_serializer.save()
            else:
                raise serializers.ValidationError({"error": "Academic record update failed. Please check the provided data."})

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    # --- cross-field validation ---
    def validate(self, data):
        # Ensure family (if set) belongs to branch
        branch = data.get('denomination_branch') or getattr(self.instance, 'denomination_branch', None)
        family = data.get('denomination_family', None)
        if family:
            allowed = FAMILIES_BY_BRANCH.get(branch, set())
            if family not in allowed:
                raise serializers.ValidationError({"denomination_family": "Family not allowed for selected branch."})
        return data

    # --- simple field validations ---
    def validate_biography(self, value):
        # ensure biography <= 2000 chars
        if value and len(value) > 2000:
            raise serializers.ValidationError({"error": "Biography cannot exceed 1000 characters."})
        return value

    def validate_vision(self, value):
        # ensure vision <= 2000 chars
        if value and len(value) > 2000:
            raise serializers.ValidationError({"error": "Vision cannot exceed 1000 characters."})
        return value

    # -------------------------------
    def validate_spiritual_rebirth_day(self, value):
        # Ensure not in the future
        if value and value > timezone.now().date():
            raise serializers.ValidationError({"error": "Spiritual rebirth day cannot be in the future."})
        return value

    # --- litcovenant (hardened for safety) ---
    def get_litcovenant(self, obj):
        """
        Return only non-sensitive covenant relationships for the owner profile.
        Even if:
          - show_fellowship_in_profile = True
          - pin_security_enabled = True
        we NEVER expose 'Confidant' or 'Entrusted' via this serializer.
        """
        # Respect visibility flag
        if not getattr(obj, 'show_fellowship_in_profile', False):
            return []

        user = obj.user
        request = self.context.get('request')

        qs = (
            Fellowship.objects
            .filter(Q(from_user=user) | Q(to_user=user), status='Accepted')
            .select_related(
                'from_user', 'to_user',
                'from_user__member_profile', 'to_user__member_profile'
            )
        )

        out, seen = [], set()
        fellowship_ids_map = {}

        for f in qs:
            # Decide relationship type and opposite user from POV of profile owner
            if f.from_user_id == user.id:
                rel_type = f.fellowship_type
                opposite_user = f.to_user
            else:
                rel_type = f.reciprocal_fellowship_type
                opposite_user = f.from_user

            # 🔒 Hard rule: never expose highly sensitive relationships
            if rel_type in ("Confidant", "Entrusted"):
                continue

            key = (opposite_user.id, rel_type)
            if key in seen:
                continue
            seen.add(key)

            out.append(f)
            fellowship_ids_map[opposite_user.id] = f.id

        # Pass fellowship_ids map so frontend can know which id to use for actions
        ctx = {'request': request, 'fellowship_ids': fellowship_ids_map}
        return FellowshipSerializer(out, many=True, context=ctx).data


    # --- spiritual_gifts (unchanged) ---
    def get_spiritual_gifts(self, obj):
        if not getattr(obj, 'show_gifts_in_profile', False):
            return None
        msg = (
            MemberSpiritualGifts.objects
            .filter(member=obj)
            .prefetch_related('gifts')
            .order_by('-created_at')
            .first()
        )
        if not msg:
            return None
        return MemberSpiritualGiftsSerializer(msg, context={'request': self.context.get('request')}).data
    
    # --- friends (randomized, seedable, future-weighted) ---
    def get_friends(self, obj):  # one-liner
        return self._build_friends_payload(obj)


# PUBLIC Member Serializer -----------------------------------------------------------
class PublicMemberSerializer(FriendsBlockMixin, serializers.ModelSerializer):
    # --- user (privacy handled in PublicCustomUserSerializer) ---
    user = PublicCustomUserSerializer(read_only=True)

    # --- read-only nested/derived blocks ---
    service_types = MemberServiceTypeSerializer(many=True, read_only=True)
    academic_record = serializers.SerializerMethodField()
    spiritual_gifts = serializers.SerializerMethodField()
    social_links = serializers.SerializerMethodField()
    friends = serializers.SerializerMethodField()
    litcovenant = serializers.SerializerMethodField()
    testimonies = serializers.SerializerMethodField()

    # --- NEW: expose branch/family values + their display labels ---
    denomination_branch = serializers.CharField(read_only=True)
    denomination_family = serializers.CharField(read_only=True, allow_null=True)

    denomination_branch_label = serializers.SerializerMethodField()
    denomination_family_label = serializers.SerializerMethodField()

    # --- BACKWARD COMPAT ---
    denominations_type = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = [
            'user',
            'biography', 'vision', 'spiritual_rebirth_day',
            'denomination_branch', 'denomination_branch_label',
            'denomination_family', 'denomination_family_label',
            'denominations_type',
            'service_types', 'organization_memberships',
            'academic_record', 'spiritual_gifts',
            'social_links', 'friends', 'litcovenant', 'testimonies',
            'show_gifts_in_profile', 'show_fellowship_in_profile', 'hide_confidants',
            'register_date', 
            'is_townlit_verified', 'townlit_verified_at',
            'is_privacy', 'is_hidden_by_confidants', 'is_migrated', 'is_active',
        ]
        read_only_fields = fields

    def get_fields(self):
        # Lazy import to avoid circular deps
        fields = super().get_fields()
        from apps.profilesOrg.serializers import OrganizationSerializer
        fields['organization_memberships'] = OrganizationSerializer(many=True, read_only=True)
        return fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep request context for nested serializers
        self.fields['user'] = PublicCustomUserSerializer(context=self.context, read_only=True)

    # --- labels ---
    def get_denomination_branch_label(self, obj: Member):
        try:
            label = obj.get_denomination_branch_display()
            return label or _titleize_slug(obj.denomination_branch or "")
        except Exception:
            return _titleize_slug(obj.denomination_branch or "")

    def get_denomination_family_label(self, obj: Member):
        if not obj.denomination_family:
            return None
        try:
            label = obj.get_denomination_family_display()
            return label or _titleize_slug(obj.denomination_family)
        except Exception:
            return _titleize_slug(obj.denomination_family)

    def get_denominations_type(self, obj: Member):
        return obj.denomination_family or None

    # --- academic record ---
    def get_academic_record(self, obj: Member):
        if not obj.academic_record_id:
            return None
        return AcademicRecordSerializer(obj.academic_record, context=self.context).data

    # --- spiritual gifts ---
    def get_spiritual_gifts(self, obj: Member):
        if not getattr(obj, 'show_gifts_in_profile', False):
            return None
        from apps.profiles.models import MemberSpiritualGifts
        msg = (
            MemberSpiritualGifts.objects
            .filter(member=obj)
            .prefetch_related('gifts')
            .order_by('-created_at')
            .first()
        )
        if not msg:
            return None
        from apps.profiles.serializers import MemberSpiritualGiftsSerializer
        return MemberSpiritualGiftsSerializer(msg, context=self.context).data

    # --- social links ---
    def get_social_links(self, obj: Member):
        links_qs = social_links_for_user(obj.user)
        return SocialMediaLinkReadOnlySerializer(links_qs, many=True, context=self.context).data

    # --- friends (randomized, seedable, future-weighted) ---
    def get_friends(self, obj):  # one-liner
        return self._build_friends_payload(obj)
    
    # --- litcovenant ---
    def get_litcovenant(self, obj: Member):
        """
        Visitor-safe covenant list:
        - Never expose highly sensitive relationships (Confidant, Entrusted) to frontend.
        """
        qs = fellowships_visible(obj)

        # Exclude sensitive types on either side of the covenant
        safe_qs = qs.exclude(
            fellowship_type__in=["Confidant", "Entrusted"]
        ).exclude(
            reciprocal_fellowship_type__in=["Confidant", "Entrusted"]
        )
        return FellowshipSerializer(safe_qs, many=True, context=self.context).data

    # --- testimonies ---
    def get_testimonies(self, obj):
        try:
            request = self.context.get("request")

            # ✅ viewer must be CustomUser, not Member
            viewer = (
                request.user
                if request and request.user.is_authenticated
                else None
            )

            qs = get_visible_posts(
                model=Testimony,
                owner=obj,      # profile owner (Member)
                viewer=viewer,  # viewer (CustomUser)
            )

            def pick(ttype):
                return qs.filter(type=ttype).first()

            ctx = {"request": request} if request else {}

            return {
                "audio": (
                    TestimonySerializer(pick(Testimony.TYPE_AUDIO), context=ctx).data
                    if pick(Testimony.TYPE_AUDIO)
                    else None
                ),
                "video": (
                    TestimonySerializer(pick(Testimony.TYPE_VIDEO), context=ctx).data
                    if pick(Testimony.TYPE_VIDEO)
                    else None
                ),
                "written": (
                    TestimonySerializer(pick(Testimony.TYPE_WRITTEN), context=ctx).data
                    if pick(Testimony.TYPE_WRITTEN)
                    else None
                ),
            }

        except Exception as e:
            logger.exception(
                "[PublicMemberSerializer] get_testimonies FAILED | member_id=%s | error=%s",
                obj.id,
                e,
            )
            raise


# LIMITED Member Serializer -----------------------------------------------------------
class LimitedMemberSerializer(serializers.ModelSerializer):
    """
    Ultra-minimal public view of Member when privacy/visibility is restricted.
    Exposes only identity-safe verification flags + nested user.
    """
    user = LimitedCustomUserSerializer(read_only=True)

    class Meta:
        model = Member
        fields = [
            'user',
            'is_townlit_verified',
            'townlit_verified_at',
        ]
        read_only_fields = fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep context for nested user serializer
        self.fields['user'] = LimitedCustomUserSerializer(
            context=self.context,
            read_only=True
        )


    
# MEMBER'S GIFT serializer -----------------------------------------------------------------------------
# Spritual Gifts
class SpiritualGiftSerializer(serializers.ModelSerializer):
    name_display = serializers.CharField(source='get_name_display', read_only=True)

    class Meta:
        model = SpiritualGift
        fields = ['id', 'name', 'name_display', 'description']
        

# Gift Question serializer
class SpiritualGiftSurveyQuestionSerializer(serializers.ModelSerializer):
    gift = SpiritualGiftSerializer()

    class Meta:
        model = SpiritualGiftSurveyQuestion
        fields = ['id', 'question_text', 'question_number', 'language', 'options', 'gift']
        
# Gift Survey serializer
class SpiritualGiftSurveyResponseSerializer(serializers.ModelSerializer):
    question = SpiritualGiftSurveyQuestionSerializer()

    class Meta:
        model = SpiritualGiftSurveyResponse
        fields = ['id', 'member', 'question', 'answer']
        
    def validate_answer(self, value):
        if value < 1 or value > 7:
            raise serializers.ValidationError("Answer must be between 1 and 7.")
        return value

    def validate(self, data):
        question = data.get('question')
        member = data.get('member')
        if not SpiritualGiftSurveyQuestion.objects.filter(id=question.id).exists():
            raise serializers.ValidationError("The question is not valid.")
        if not Member.objects.filter(user=member).exists():
            raise serializers.ValidationError("The member is not valid.")
        return data
        
# Member Gifts serializer
class MemberSpiritualGiftsSerializer(serializers.ModelSerializer):
    gifts = SpiritualGiftSerializer(many=True)
    survey_results = serializers.JSONField()

    class Meta:
        model = MemberSpiritualGifts
        fields = ['member', 'gifts', 'survey_results', 'created_at']
        
        
        
        




# GUESTUSER serializer ----------------------------------------------------------------------------------
class GuestUserSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)

    class Meta:
        model = GuestUser
        fields = ['user', 'register_date', 'is_migrated', 'is_active', 'slug']
        read_only_fields = ['user', 'register_date', 'is_migrated', 'is_active', 'slug']

    def update(self, instance, validated_data):
        # Update CustomUser fields
        custom_user_data = validated_data.pop('user', None)
        if custom_user_data:
            custom_user_serializer = CustomUserSerializer(instance.user, data=custom_user_data, partial=True)
            if custom_user_serializer.is_valid():
                custom_user_serializer.save()


# LIMITED GUESTUSER serializer -----------------------------------------------------------------
class LimitedGuestUserSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())

    class Meta:
        model = GuestUser
        fields = ['user', 'register_date', 'slug']
        read_only_fields = ['user', 'register_date', 'slug']

    
# CLIENT serializer ------------------------------------------------------------------ 
# Client Request 
class ClientRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientRequest
        fields = ['id', 'request', 'description', 'document_1', 'document_2', 'register_date', 'is_active']
        read_only_fields = ['register_date']

    def validate_document_1(self, value):
        if value and value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("The document size exceeds the limit of 2MB.")
        valid_file_types = ['application/pdf', 'image/jpeg', 'image/png']
        if value and value.content_type not in valid_file_types:
            raise serializers.ValidationError("Only PDF, JPEG, and PNG files are allowed.")
        return value

    def validate_document_2(self, value):
        if value and value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("The document size exceeds the limit of 2MB.")
        valid_file_types = ['application/pdf', 'image/jpeg', 'image/png']
        if value and value.content_type not in valid_file_types:
            raise serializers.ValidationError("Only PDF, JPEG, and PNG files are allowed.")
        return value

    def validate(self, data):
        if not data.get('document_1') and not data.get('document_2'):
            raise serializers.ValidationError("At least one document should be uploaded.")
        return data
           
# Client ----------------------------------------------------------------------------
class ClientSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())
    # lazy: organization_clients را در get_fields اضافه می‌کنیم
    request = ClientRequestSerializer(read_only=True)

    class Meta:
        model = Client
        fields = ['user', 'organization_clients', 'request', 'register_date', 'is_active', 'slug']
        read_only_fields = ['register_date', 'slug']

    def get_fields(self):
        fields = super().get_fields()
        # ✅ Lazy import to avoid circular imports
        fields['organization_clients'] = SimpleOrganizationSerializer(many=True, read_only=True)
        return fields

    def validate(self, data):
        if data.get('is_active') and not data.get('request'):
            raise serializers.ValidationError("Active client must have a request.")
        return data
    
    
# CUSTOMER serializer ------------------------------------------------------------------ 
class CustomerSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())
    billing_address = AddressSerializer(read_only=True)
    shipping_addresses = AddressSerializer(many=True, read_only=True)
    customer_phone_number = serializers.CharField(
        max_length=20, 
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")]
    )
    
    class Meta:
        model = Customer
        fields = ['user', 'billing_address', 'shipping_addresses', 'customer_phone_number', 'register_date', 'deactivation_reason', 'deactivation_note', 'is_active']
        read_only_fields = ['user', 'register_date', 'is_active']

    def validate_shipping_addresses(self, value):
        if not value:
            raise serializers.ValidationError("Shipping addresses cannot be empty.")
        return value
# apps/profiles/serializers/member.py

import logging

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.profiles.helpers.social_links import social_links_for_user
from apps.profiles.helpers.fellowships import fellowships_visible
from apps.profiles.friends_priority.service import get_friends_for_profile
from apps.profiles.models.relationships import Fellowship
from apps.profiles.models.member import Member
from apps.profiles.models.academic import AcademicRecord
from apps.profiles.models.gifts import MemberSpiritualGifts
from apps.profilesOrg.constants_denominations import (
    CHURCH_BRANCH_CHOICES,
    CHURCH_FAMILY_CHOICES_ALL,
    FAMILIES_BY_BRANCH,
)
from apps.accounts.serializers.user_serializers import (
    CustomUserSerializer,
    PublicCustomUserSerializer,
    LimitedCustomUserSerializer,
    SimpleCustomUserSerializer,
)
from apps.accounts.serializers.social_serializers import SocialMediaLinkReadOnlySerializer
from apps.posts.services.feed_access import get_visible_posts
from apps.posts.models.testimony import Testimony
from apps.posts.serializers.testimonies import TestimonySerializer

from apps.profiles.serializers.academic import AcademicRecordSerializer
from apps.profiles.serializers.services import MemberServiceTypeSerializer
from apps.profiles.serializers.fellowships import FellowshipSerializer
from apps.profiles.serializers.gifts import MemberSpiritualGiftsSerializer

logger = logging.getLogger(__name__)


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

        try:
            friends = get_friends_for_profile(
                member_obj.user,
                random=random_flag,
                daily=daily_flag,
                seed=seed,
                limit=limit,
            )
            return SimpleCustomUserSerializer(friends, many=True, context=self.context).data
        except Exception:
            # Never break profile response
            logger.exception("friends block failed for user_id=%s", getattr(member_obj.user, "id", None))
            return []


# MEMBER Serializer ------------------------------------------------------------------------------
def _titleize_slug(value: str) -> str:
    # Fallback: "roman_catholicism" -> "Roman Catholicism"
    if not value:
        return value
    return value.replace("_", " ").title()

class MemberSerializer(FriendsBlockMixin, serializers.ModelSerializer):
    user = CustomUserSerializer(context=None)
    service_types = MemberServiceTypeSerializer(many=True, read_only=True)
    academic_record = AcademicRecordSerializer(required=False, allow_null=True)
    litcovenant = serializers.SerializerMethodField()
    spiritual_gifts = serializers.SerializerMethodField()

    friends = serializers.SerializerMethodField()

    # Editable fields (kept as before)
    denomination_branch = serializers.ChoiceField(
        choices=CHURCH_BRANCH_CHOICES, required=False, allow_null=True, allow_blank=False
    )
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
    denomination_branch = serializers.CharField(read_only=True, allow_null=True)
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
            viewer = request.user if request and request.user.is_authenticated else None

            qs = get_visible_posts(
                model=Testimony,
                owner=obj,      # profile owner (Member)
                viewer=viewer,  # viewer (CustomUser)
            )

            def pick(ttype):
                return qs.filter(type=ttype).first()

            ctx = {"request": request} if request else {}

            def serialize_or_none(instance: Testimony | None):
                if not instance:
                    return None

                # ✅ Public rule:
                # If media is not converted yet, DO NOT expose it at all.
                # This prevents clickable empty poster + premature notifications/visibility.
                if instance.type in [Testimony.TYPE_VIDEO, Testimony.TYPE_AUDIO] and not getattr(instance, "is_converted", False):
                    return None

                return TestimonySerializer(instance, context=ctx).data

            return {
                "audio": serialize_or_none(pick(Testimony.TYPE_AUDIO)),
                "video": serialize_or_none(pick(Testimony.TYPE_VIDEO)),
                "written": serialize_or_none(pick(Testimony.TYPE_WRITTEN)),
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


# SIMPLE MEMBER Serializers ------------------------------------------------------------------------    
class SimpleMemberSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()
    class Meta:
        model = Member
        fields = ['id', 'profile_image','slug']
        read_only_fields = ['id', 'slug']
        
    def get_profile_image(self, obj):
        request = self.context.get('request')
        if obj.id.image_name:
            return request.build_absolute_uri(obj.id.image_name.url) if request else obj.id.image_name.url
        return None



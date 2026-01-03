# posts/serializers_owner_min.py
# ======================================================================
#  OwnerDTO serializer (FINAL – flat, frontend-aligned)
# ======================================================================

import logging
from django.urls import reverse
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType

from apps.core.ownership.utils import resolve_owner_from_request
from apps.accounts.models import CustomUser
from apps.accounts.serializers import CustomLabelSerializer
from apps.profiles.models import Member, GuestUser
from apps.profilesOrg.models import Organization
from common.file_handlers.org_logo import OrganizationLogoMixin
from django.core.exceptions import DisallowedHost
logger = logging.getLogger(__name__)


# ======================================================================
# Base helpers
# ======================================================================

def _absolute(request, path: str | None) -> str | None:
    if not path:
        return None

    if not request:
        return path

    try:
        return request.build_absolute_uri(path)
    except DisallowedHost:
        # ⛑ never crash serialization because of host
        return path
    except Exception:
        return path


# ======================================================================
# Owner → CustomUser / Member / Guest
# ======================================================================

class OwnerUserDTO(serializers.ModelSerializer):
    """
    Produces OwnerDTO-compatible payload for:
    - CustomUser
    - Member.user
    - GuestUser.user
    """

    type = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    is_townlit_verified = serializers.SerializerMethodField()
    label = CustomLabelSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "type",
            "id",
            "username",
            "name",
            "family",
            "avatar_url",
            "profile_url",
            "is_verified_identity",
            "is_townlit_verified",
            "label",
        ]
        read_only_fields = fields

    # --------------------------------------------------
    # Owner type resolution
    # --------------------------------------------------
    def get_type(self, obj: CustomUser) -> str:
        """
        Order matters:
        Member > Guest > CustomUser
        """
        if hasattr(obj, "member_profile"):
            return "member"
        if hasattr(obj, "guest_profile"):
            return "guest"
        return "customUser"

    # --------------------------------------------------
    # URLs
    # --------------------------------------------------
    def get_profile_url(self, obj: CustomUser) -> str | None:
        request = self.context.get("request")
        if not obj.username:
            return None
        return _absolute(request, f"/u/{obj.username}/")

    def get_avatar_url(self, obj: CustomUser) -> str | None:
        request = self.context.get("request")
        try:
            path = reverse("main:main-avatar-detail", args=[obj.id])
        except Exception:
            return None
        return _absolute(request, path)

    # --------------------------------------------------
    # Derived flags
    # --------------------------------------------------
    def get_is_townlit_verified(self, obj: CustomUser) -> bool:
        mp = getattr(obj, "member_profile", None)
        return bool(mp and mp.is_townlit_verified)


# ======================================================================
# Owner → Organization
# ======================================================================

class OwnerOrganizationDTO(OrganizationLogoMixin, serializers.ModelSerializer):
    """
    Produces OwnerDTO-compatible payload for Organization
    """

    type = serializers.SerializerMethodField()
    name = serializers.CharField(source="org_name", read_only=True)
    profile_url = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "type",
            "id",
            "name",
            "slug",
            "logo_url",      # injected by OrganizationLogoMixin
            "profile_url",
        ]
        read_only_fields = fields

    def get_type(self, obj) -> str:
        return "organization"

    def get_profile_url(self, obj) -> str | None:
        request = self.context.get("request")
        try:
            url = reverse(
                getattr(obj, "url_name", "organization_detail"),
                kwargs={"slug": obj.slug},
            )
        except Exception:
            url = f"/organizations/{obj.slug}/"

        return _absolute(request, url)


# ======================================================================
# Public builder (used by Moments / Posts / Comments / Reactions)
# ======================================================================

def build_owner_dto_from_content_object(obj, *, context=None):
    """
    Returns a flat OwnerDTO dict or None

    Supported targets:
    - CustomUser
    - Member
    - GuestUser
    - Organization

    Adds:
    - is_me: bool (true if this owner belongs to current request user)
    """

    try:
        request = context.get("request") if context else None

        # --------------------------------------------------
        # Resolve target (GFK-safe)
        # --------------------------------------------------
        target = getattr(obj, "content_object", None)

        if target is None:
            ct = getattr(obj, "content_type", None)
            oid = getattr(obj, "object_id", None)
            if ct and oid:
                ModelClass = ct.model_class()
                if ModelClass:
                    try:
                        target = ModelClass.objects.get(pk=oid)
                    except ModelClass.DoesNotExist:
                        return None

        if target is None:
            return None

        # --------------------------------------------------
        # Resolve request owner (Member / Guest / Org)
        # --------------------------------------------------
        request_owner = None
        if request and request.user.is_authenticated:
            request_owner = resolve_owner_from_request(request)

        def compute_is_me(target_obj) -> bool:
            if not request_owner:
                return False
            try:
                owner_ct = ContentType.objects.get_for_model(
                    request_owner.__class__
                )
                target_ct = ContentType.objects.get_for_model(
                    target_obj.__class__
                )
                return (
                    owner_ct.id == target_ct.id
                    and request_owner.id == target_obj.id
                )
            except Exception:
                return False

        # --------------------------------------------------
        # Organization
        # --------------------------------------------------
        if isinstance(target, Organization):
            dto = OwnerOrganizationDTO(target, context=context).data
            dto["is_me"] = compute_is_me(target)
            return dto

        # --------------------------------------------------
        # Member / GuestUser → underlying CustomUser
        # --------------------------------------------------
        if isinstance(target, Member):
            dto = OwnerUserDTO(target.user, context=context).data
            dto["is_me"] = compute_is_me(target)
            return dto

        if isinstance(target, GuestUser):
            dto = OwnerUserDTO(target.user, context=context).data
            dto["is_me"] = compute_is_me(target)
            return dto

        # --------------------------------------------------
        # Direct CustomUser
        # --------------------------------------------------
        if isinstance(target, CustomUser):
            dto = OwnerUserDTO(target, context=context).data
            dto["is_me"] = compute_is_me(target)
            return dto

        return None

    except Exception:
        logger.exception("🔥 build_owner_dto_from_content_object failed")
        return None
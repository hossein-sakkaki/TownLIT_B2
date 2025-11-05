# posts/serializers_owner_min.py
from rest_framework import serializers
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.accounts.serializers import CustomLabelSerializer
from common.file_handlers.profile_image import ProfileImageMixin
from common.file_handlers.org_logo import OrganizationLogoMixin
from apps.profilesOrg.models import Organization  
from apps.profiles.models import Member  
from django.contrib.contenttypes.models import ContentType

# ---- Owner (User) ----
class OwnerMinCustomUserSerializer(ProfileImageMixin, serializers.ModelSerializer):
    """
    Minimal, public owner shape for a CustomUser.
    - Provides `profile_image_url` via ProfileImageMixin (image_name -> *_url)
    - Includes `label` and `is_verified_identity`
    """
    label = CustomLabelSerializer(read_only=True)
    is_verified_identity = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id", "username", "name", "family",
            "label", "is_verified_identity",
            # profile_image_url comes from ProfileImageMixin (rename in mixin)
            "profile_url",
        ]
        read_only_fields = fields

    def get_is_verified_identity(self, obj):
        return getattr(getattr(obj, "member_profile", None), "is_verified_identity", False)

    def get_profile_url(self, obj):
        # Use your existing user absolute-url logic if any; otherwise reverse by username
        try:
            return obj.get_absolute_url()
        except Exception:
            # Fallback: build a URL pattern you support, e.g. /u/<username>/
            request = self.context.get("request")
            url = f"/u/{obj.username}/"
            return request.build_absolute_uri(url) if request else url


# ---- Owner (Organization) ----
class OwnerMinOrganizationSerializer(OrganizationLogoMixin, serializers.ModelSerializer):
    """
    Minimal, public owner shape for an Organization.
    - Provides `logo_url` via OrganizationLogoMixin
    - Exposes `org_name`, `slug`, `is_verified`, and a `profile_url`
    """
    profile_url = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id", "slug", "org_name",
            "is_verified",
            # logo_url is injected by the mixin
            "profile_url",
        ]
        read_only_fields = fields

    def get_profile_url(self, obj):
        """
        Prefer reversing by your declared "url_name" if available.
        According to your model: url_name = 'organization_detail'
        It likely resolves by slug; adjust kwargs as needed.
        """
        request = self.context.get("request")
        try:
            url = reverse(getattr(obj, "url_name", "organization_detail"), kwargs={"slug": obj.slug})
        except Exception:
            # Fallback to a conventional path if reversing fails
            url = f"/organizations/{obj.slug}/"
        return request.build_absolute_uri(url) if (request and not url.startswith("http")) else url



def build_owner_union_from_content_object(obj, context=None) -> dict | None:
    """
    Return a union dict with normalized owner:
      - {"kind": "customUser",   "data": OwnerMinCustomUserSerializer(...).data}
      - {"kind": "organization", "data": OwnerMinOrganizationSerializer(...).data}
      - None if cannot resolve
    """
    # Prefer generic relation if present
    target = getattr(obj, "content_object", None)

    # Fallback: resolve via content_type/object_id
    if target is None:
        ct = getattr(obj, "content_type", None)
        oid = getattr(obj, "object_id", None)
        if ct and oid:
            ModelClass = ct.model_class()
            if ModelClass:
                try:
                    target = ModelClass.objects.get(pk=oid)
                except ModelClass.DoesNotExist:
                    target = None

    if target is None:
        return None

    # Member -> map to target.user (CustomUser)
    if isinstance(target, Member):
        cu = target.user
        data = OwnerMinCustomUserSerializer(instance=cu, context=context).data
        return {"kind": "customUser", "data": data}

    # Organization -> map as organization owner
    if isinstance(target, Organization):
        data = OwnerMinOrganizationSerializer(instance=target, context=context).data
        return {"kind": "organization", "data": data}

    # Unknown
    return None
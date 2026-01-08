# apps/posts/views/testimonies.py

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.db.models import F

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny    
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from apps.posts.models.testimony import Testimony
from apps.posts.serializers.testimonies import TestimonySerializer
from apps.core.visibility.query import VisibilityQuery
from apps.core.pagination import ConfigurablePagination, FeedCursorPagination
from apps.core.visibility.policy import VisibilityPolicy
from apps.core.ownership.utils import resolve_owner_from_request
import logging
logger = logging.getLogger(__name__)


class TestimonyViewSet(viewsets.ModelViewSet):
    """
    Testimony API (post-like)

    - Visibility-aware
    - Interaction-ready
    - Cursor feed support
    - Owner-safe
    """

    serializer_class = TestimonySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"
    lookup_url_kwarg = "slug" 
    pagination_class = ConfigurablePagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # -------------------------------------------------
    # Permissions (Visitor-safe)
    # -------------------------------------------------
    def get_permissions(self):
        """
        Allow public access ONLY for safe read actions.
        """
        if self.action in [
            "retrieve",   # public watch page needs this
            "explore",    # public discover
        ]:
            return [AllowAny()]

        return super().get_permissions()

    # -------------------------------------------------
    # Base queryset (ordering only)
    # -------------------------------------------------
    def get_queryset(self):
        base = (
            Testimony.objects
            .select_related("content_type")
            .order_by("-published_at", "-id")
        )

        # IMPORTANT: retrieve must not be pre-filtered by Query
        if self.action == "retrieve":
            return base

        # public explore (visitor-safe)
        if self.action == "explore" and not self.request.user.is_authenticated:
            return base.filter(visibility="global")  # keep existing behavior

        # IMPORTANT: Query should use request.user for consistency
        return VisibilityQuery.for_viewer(
            viewer=self.request.user,
            base_queryset=base,
        )



    # -------------------------------------------------
    # Owner resolver
    # -------------------------------------------------
    def _get_owner(self):
        return resolve_owner_from_request(self.request)


    def _assert_is_owner(self, obj):
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied("Invalid owner context.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)
        if (
            obj.content_type_id != owner_ct.id
            or obj.object_id != owner.id
        ):
            raise PermissionDenied("You do not own this Testimony.")

    # -------------------------------------------------
    # Create
    # -------------------------------------------------
    @transaction.atomic
    def perform_create(self, serializer):
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied("Invalid owner type.")

        ttype = serializer.validated_data.get("type")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)

        # Enforce: one testimony per type per owner
        exists = Testimony.objects.filter(
            content_type=owner_ct,
            object_id=owner.id,
            type=ttype,
        ).exists()

        if exists:
            raise PermissionDenied(
                f"You already have a '{ttype}' testimony."
            )

        serializer.save(
            content_type=owner_ct,
            object_id=owner.id,
        )

    # -------------------------------------------------
    # Update
    # -------------------------------------------------
    def perform_update(self, serializer):
        obj = self.get_object()
        self._assert_is_owner(obj)
        serializer.save(updated_at=timezone.now())

    # -------------------------------------------------
    # Delete
    # -------------------------------------------------
    def perform_destroy(self, instance):
        self._assert_is_owner(instance)
        instance.delete()

    # -------------------------------------------------
    # Feed (cursor-based, home timeline)
    # -------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        pagination_class=FeedCursorPagination,
    )
    def feed(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------
    # My testimonies (owner-only)
    # -------------------------------------------------
    @action(detail=False, methods=["get"])
    def me(self, request):
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied("Invalid owner type.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)

        qs = self.get_queryset().filter(
            content_type_id=owner_ct.id,
            object_id=owner.id,
        )

        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------
    # Explore (public discover)
    # -------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
    )
    def explore(self, request):
        qs = self.get_queryset()  # already visitor-safe
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


    # -------------------------------------------------
    # Profile summary (1 per type)
    # -------------------------------------------------
    @action(detail=False, methods=["get"])
    def summary(self, request):
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied("Invalid owner type.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)
        qs = Testimony.objects.filter(
            content_type=owner_ct,
            object_id=owner.id,
        )

        def pack(ttype):
            t = qs.filter(type=ttype).first()
            if not t:
                return {"exists": False}
            data = {
                "exists": True,
                "id": t.id,
                "slug": t.slug,
                "title": t.title,
                "published_at": t.published_at,
                "is_converted": t.is_converted,
            }
            if t.type == Testimony.TYPE_WRITTEN:
                excerpt = (
                    t.content[:140] + "…"
                    if t.content and len(t.content) > 140
                    else t.content
                )
                data["excerpt"] = excerpt
            return data

        return Response({
            "audio": pack(Testimony.TYPE_AUDIO),
            "video": pack(Testimony.TYPE_VIDEO),
            "written": pack(Testimony.TYPE_WRITTEN),
        })

    def _resolve_owner_object(self, obj):
        """
        Resolve owner object from (content_type, object_id).
        Returns model instance (e.g., Member / Organization / CustomUser) or None.
        """
        try:
            ct = obj.content_type
            if not ct or not obj.object_id:
                return None

            model_cls = ct.model_class()
            if not model_cls:
                return None

            return model_cls.objects.filter(pk=obj.object_id).first()
        except Exception:
            logger.exception("Failed to resolve testimony owner object")
            return None


    def _resolve_owner_user_and_member(self, obj):
        """
        Normalize owner into:
        - owner_user: CustomUser or None
        - owner_member: Member or None (where is_privacy lives)
        - owner_obj: raw resolved owner object (Member/Org/User/...)
        """
        owner_obj = self._resolve_owner_object(obj)
        if not owner_obj:
            return None, None, None

        # Case A) owner is Member -> user lives on member.user
        # NOTE: adjust attribute name if your Member uses a different field name
        if hasattr(owner_obj, "user"):
            owner_user = getattr(owner_obj, "user", None)
            owner_member = owner_obj  # privacy is on Member itself
            return owner_user, owner_member, owner_obj

        # Case B) owner is CustomUser directly -> member is user.member_profile
        try:
            from apps.accounts.models import CustomUser  # adjust if needed
            if isinstance(owner_obj, CustomUser):
                owner_user = owner_obj
                owner_member = getattr(owner_user, "member_profile", None)  # related_name you mentioned ✅
                return owner_user, owner_member, owner_obj
        except Exception:
            logger.exception("CustomUser import/type check failed")

        # Other owners (Organization, GuestUser, etc.)
        return None, None, owner_obj



    # -------------------------------------------------
    # Retrieve (public-safe, analytics counted)
    # -------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()

        # -------------------------------------------------
        # 0) Profile-privacy redirect gate (anon/outsiders)
        # -------------------------------------------------
        try:
            viewer = request.user if request.user.is_authenticated else None

            owner_user, owner_member, owner_obj = self._resolve_owner_user_and_member(obj)

            # Debug prints (temporary)
            print("owner_obj:", type(owner_obj).__name__ if owner_obj else None)
            print("owner_user:", getattr(owner_user, "username", None) if owner_user else None)
            print("owner_member_privacy:", getattr(owner_member, "is_privacy", None) if owner_member else None)

            # Only apply when we have a member privacy flag + a user username
            if owner_user and owner_member and getattr(owner_member, "is_privacy", False):
                # Owner can view
                if viewer and viewer.id == owner_user.id:
                    pass
                else:
                    # Optional friend check (if you have it)
                    is_friend = False
                    try:
                        # is_friend = self._is_friend(viewer, owner_user)
                        pass
                    except Exception:
                        logger.exception("Friendship check failed")

                    if not is_friend:
                        return Response(
                            {
                                "profile_gate": {
                                    "key": "profile_privacy_redirect",
                                    "reason": "private_profile",
                                    "redirect_to": f"/lit/{owner_user.username}",
                                }
                            },
                            status=status.HTTP_200_OK,
                        )
        except Exception:
            logger.exception("profile_gate check failed")

        # -------------------------------------------------
        # 1) Visibility gate (content-level policy)
        # -------------------------------------------------
        reason = VisibilityPolicy.gate_reason(viewer=request.user, obj=obj)
        if reason is not None:
            return Response(
                {
                    "detail": "Access restricted.",
                    "code": reason,  # "login_required" | "forbidden" | "hidden"
                    "content_type": "testimony",
                    "slug": obj.slug,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -------------------------------------------------
        # 2) Analytics (safe)
        # -------------------------------------------------
        try:
            Testimony.objects.filter(pk=obj.pk).update(
                view_count_internal=F("view_count_internal") + 1,
                last_viewed_at=timezone.now(),
            )
        except Exception:
            logger.exception("testimony analytics update failed")

        serializer = self.get_serializer(obj)
        return Response(serializer.data)
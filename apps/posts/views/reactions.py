from django.contrib.contenttypes.models import ContentType
from django.db import models


from rest_framework import status, viewsets, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from apps.posts.serializers.reactions import ReactionSerializer

from apps.posts.models import Reaction
from apps.accounts.serializers import SimpleCustomUserSerializer

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# REACTIONS Viewset --------------------------------------------------------------------------
class ReactionViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Centralized reactions endpoint.
    POST /posts/reactions/ (toggle)
    GET  /posts/reactions/?content_type=testimony&object_id=42
    GET  /posts/reactions/summary/?content_type=testimony&object_id=42
    DELETE /posts/reactions/<id>/  (owner-only)
    """
    queryset = Reaction.objects.all().select_related('name', 'content_type')
    serializer_class = ReactionSerializer
    permission_classes = [IsAuthenticated]  # default

    def get_queryset(self):
        qs = super().get_queryset()
        ct = self.request.query_params.get('content_type')
        oid = self.request.query_params.get('object_id')

        if ct and oid:
            # allow id, app.model, or model
            try:
                if str(ct).isdigit():
                    cto = ContentType.objects.get(pk=int(ct))
                elif '.' in str(ct):
                    app_label, model = str(ct).split('.', 1)
                    cto = ContentType.objects.get(app_label=app_label, model=model)
                else:
                    cto = ContentType.objects.get(model=str(ct))
            except ContentType.DoesNotExist:
                return Reaction.objects.none()

            qs = qs.filter(content_type=cto, object_id=oid)

        return qs.order_by('-timestamp')

    def perform_destroy(self, instance):
        # only owner can delete
        if instance.name_id != self.request.user.id:
            raise PermissionError("Forbidden")
        return super().perform_destroy(instance)

    def create(self, request, *args, **kwargs):
        """
        Toggle logic (single reaction per user per object):
        - If same reaction exists → delete → 204
        - Else remove any previous reaction for same object, then create new → 201
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        ct = serializer.validated_data['content_type']
        oid = serializer.validated_data['object_id']
        rtype = serializer.validated_data['reaction_type']

        # 1️⃣ Check if the same reaction already exists → toggle off
        existing_same = Reaction.objects.filter(
            name=user, content_type=ct, object_id=oid, reaction_type=rtype
        ).first()

        if existing_same:
            existing_same.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        # 2️⃣ Delete all other reactions by this user for the same object
        Reaction.objects.filter(
            name=user, content_type=ct, object_id=oid
        ).exclude(reaction_type=rtype).delete()

        # 3️⃣ Create the new reaction
        instance = serializer.save()
        out = self.get_serializer(instance)
        return Response(out.data, status=status.HTTP_201_CREATED)



    @action(detail=False, methods=['get'], url_path='summary', permission_classes=[AllowAny])
    def summary(self, request):
        """Count per reaction_type for a given object."""
        ct = request.query_params.get('content_type')
        oid = request.query_params.get('object_id')

        if not ct or not oid:
            return Response({'detail': 'content_type and object_id required'}, status=400)

        # resolve CT
        try:
            if str(ct).isdigit():
                cto = ContentType.objects.get(pk=int(ct))
            elif '.' in str(ct):
                app_label, model = str(ct).split('.', 1)
                cto = ContentType.objects.get(app_label=app_label, model=model)
            else:
                cto = ContentType.objects.get(model=str(ct))
        except ContentType.DoesNotExist:
            return Response({'detail': 'Invalid content type'}, status=400)

        # aggregate counts
        qs = (
            Reaction.objects.filter(content_type=cto, object_id=oid)
            .values('reaction_type')
            .annotate(count=models.Count('id'))
        )
        return Response(list(qs), status=200)

    @action(detail=False, methods=['get'], url_path='mine', permission_classes=[IsAuthenticated])
    def mine(self, request):
        """List current user's reactions (optional helper)."""
        qs = self.get_queryset().filter(name=request.user)
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        ser = self.get_serializer(qs, many=True)
        return Response(ser.data)
    
    # existing methods (get_queryset, create, etc.) --------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        url_path="with-message",
        permission_classes=[IsAuthenticated],
    )
    def with_message(self, request):
        """
        🔒 Owner-only: list reactions that include user messages for a given object.
        GET ?content_type=app.model|id|model&object_id=42[&reaction_type=...]
        """
        ct_param = request.query_params.get("content_type")
        obj_id = request.query_params.get("object_id")
        rtype = request.query_params.get("reaction_type")

        if not ct_param or not obj_id:
            return Response({"detail": "content_type and object_id required"}, status=400)

        # --- Resolve ContentType safely (accept id, app.model, or model) ---
        try:
            if str(ct_param).isdigit():
                cto = ContentType.objects.get(pk=int(ct_param))
            elif "." in str(ct_param):
                app_label, model = str(ct_param).split(".", 1)
                cto = ContentType.objects.get(app_label=app_label, model=model)
            else:
                cto = ContentType.objects.get(model=str(ct_param))
        except ContentType.DoesNotExist:
            return Response({"detail": "Invalid content type"}, status=400)

        # --- Guard: model_class() may be None for swapped/proxy/unavailable models ---
        model_cls = cto.model_class()
        if model_cls is None:
            return Response({"detail": "Target model is unavailable"}, status=400)

        # --- Cast object_id to int when possible (fallback to raw for non-int PKs) ---
        try:
            obj_pk = int(obj_id)
        except (TypeError, ValueError):
            obj_pk = obj_id

        # --- Load target object with a safe DoesNotExist branch ---
        try:
            target_obj = model_cls._default_manager.get(pk=obj_pk)
        except model_cls.DoesNotExist:
            return Response({"detail": "Target object not found"}, status=404)

        # --- Resolve real owner's user_id (handles common FK patterns + GFK drill-down) ---
        def resolve_owner_user_id(obj):
            base = obj
            # If object wraps another via GFK, drill into the real target
            if hasattr(base, "content_object") and getattr(base, "content_object") is not None:
                base = base.content_object

            # Common direct *_id fields
            for fk in ("user_id", "name_id", "owner_id", "member_user_id", "org_owner_user_id"):
                if hasattr(base, fk):
                    val = getattr(base, fk)
                    if isinstance(val, int):
                        return val

            # Member model (user OneToOne)
            if base.__class__.__name__.lower() == "member" and hasattr(base, "user_id"):
                return getattr(base, "user_id", None)

            # Related objects exposing .id
            for rel in ("name", "owner", "member_user", "org_owner_user"):
                if hasattr(base, rel):
                    rel_obj = getattr(base, rel)
                    if getattr(rel_obj, "id", None):
                        return rel_obj.id

            # Organization owners M2M (grant if requester is among owners)
            if hasattr(base, "org_owners"):
                try:
                    if base.org_owners.filter(id=request.user.id).exists():
                        return request.user.id
                except Exception:
                    pass

            return None

        owner_id = resolve_owner_user_id(target_obj)
        if owner_id != request.user.id:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        # --- Reactions WITH messages only ---
        # Store empty messages as NULL at write-time; then filter by isnull=False here.
        qs = (
            Reaction.objects
            .filter(content_type=cto, object_id=obj_pk)
            .exclude(message__isnull=True)
            .select_related("name")
            .order_by("-timestamp")
        )
        if rtype:
            qs = qs.filter(reaction_type=rtype)

        # --- Build minimal payload; skip whitespace-only after decryption (safety) ---
        items = []
        for r in qs[:200]:
            if not (r.message or "").strip():
                continue
            user_data = SimpleCustomUserSerializer(r.name, context={"request": request}).data
            items.append({
                "id": r.id,
                "reaction_type": r.reaction_type,
                "message": r.message,      # transparently decrypted by field
                "timestamp": r.timestamp,  # DRF handles datetime serialization
                "user": user_data,
            })

        return Response(items, status=200)

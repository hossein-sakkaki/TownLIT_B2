# apps/posts/views/testimonies.py
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import NotFound
import logging
logger = logging.getLogger(__name__)

from apps.posts.models import Testimony
from apps.posts.serializers.testimonies import TestimonySerializer
from apps.posts.mixins.mixins import CommentMixin, OrganizationActionMixin
from apps.profilesOrg.models import Organization, Church, MissionOrganization, ChristianPublishingHouse, ChristianCounselingCenter, ChristianWorshipMinistry, ChristianConferenceCenter, ChristianEducationalInstitution, ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization

from django.db.models import Q


# ----------------------------------------------
# 👤 MeTestimonyViewSet  (Member-owned testimonies)
# ----------------------------------------------
class MeTestimonyViewSet(CommentMixin, viewsets.GenericViewSet):
    serializer_class = TestimonySerializer
    permission_classes = [IsAuthenticated]
    queryset = Testimony.objects.all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_field = "slug"
    lookup_url_kwarg = "slug"

    def _member(self, request):
        return getattr(request.user, "member_profile", None) or getattr(request.user, "member", None)

    def _owner_qs(self, request):
        member = self._member(request)
        if not member:
            return Testimony.objects.none()
        ct = ContentType.objects.get_for_model(member.__class__)  # ← مهم
        return Testimony.objects.filter(content_type=ct, object_id=member.id)

    def get_queryset(self):
        return self._owner_qs(self.request).select_related("content_type")


    def get_object(self):
        qs = self.get_queryset()
        lookup_val = self.kwargs.get(self.lookup_url_kwarg) or self.kwargs.get("pk")
        if lookup_val is None:
            raise NotFound("Missing identifier")
        obj = qs.filter(slug=lookup_val).first()
        if obj:
            return obj
        if str(lookup_val).isdigit():
            obj = qs.filter(pk=int(lookup_val)).first()
            if obj:
                return obj
        raise NotFound("Not found")

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        return Response(
            self.get_serializer(
                obj,
                context={
                    'request': request,
                    'content_type': getattr(obj, 'content_type', None),
                    'object_id': getattr(obj, 'object_id', None),
                },
            ).data
        )


    # ---------- Summary ----------
    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        qs = self._owner_qs(request).filter(is_active=True)

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
                excerpt = (t.content[:140] + '…') if t.content and len(t.content) > 140 else t.content
                data.update({"excerpt": excerpt})
            elif t.type == Testimony.TYPE_AUDIO:
                data.update({"audio_key": getattr(t.audio, 'name', None)})
            elif t.type == Testimony.TYPE_VIDEO:
                data.update({"video_key": getattr(t.video, 'name', None)})
            return data

        return Response({
            "audio":   pack(Testimony.TYPE_AUDIO),
            "video":   pack(Testimony.TYPE_VIDEO),
            "written": pack(Testimony.TYPE_WRITTEN),
        })
        
    # ---------- Create ----------
    @action(detail=False, methods=['post'], url_path=r'create/(?P<ttype>audio|video|written)')
    @transaction.atomic
    def create_for_type(self, request, ttype=None):
        member = self._member(request)
        if not member:
            return Response(
                {"type":"about:blank","title":"Not Found","status":404,"detail":"Member profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        existing = Testimony.objects.filter(
            content_type=ContentType.objects.get_for_model(member.__class__),
            object_id=member.id,
            type=ttype,
        ).first()

        if existing:
            if request.query_params.get("replace") in ("1", "true", "yes"):
                payload = {**request.data.dict(), "type": ttype}
                for k, f in request.FILES.items():
                    payload[k] = f

                serializer = self.get_serializer(existing, data=payload, partial=True, context={'request': request})
                serializer.is_valid(raise_exception=True)
                obj = serializer.save()
                return Response(self.get_serializer(obj, context={'request': request}).data, status=status.HTTP_200_OK)

            return Response({
                "type":"about:blank","title":"Conflict","status":409,
                "detail":"Testimony already exists for this type.",
                "existing_id": existing.id, "existing_slug": existing.slug,
            }, status=status.HTTP_409_CONFLICT)
        payload = {**request.data.dict(), "type": ttype}
        for k, f in request.FILES.items():
            payload[k] = f

        serializer = self.get_serializer(data=payload, context={'request': request, 'ttype': ttype})
        serializer.is_valid(raise_exception=True)

        obj = serializer.save(
            content_type=ContentType.objects.get_for_model(member.__class__),
            object_id=member.id,
            type=ttype,
        )
        logger.info("✅ Created testimony id=%s slug=%s type=%s", obj.id, obj.slug, obj.type)

        try:
            from django.apps import apps
            T = apps.get_model('posts','Testimony')
            logger.info("✅ Created testimony id=%s (exists now? %s)",
                        obj.id, T.objects.filter(pk=obj.id).exists())
        except Exception:
            logger.exception("Post-save debug check failed")

        return Response(
            self.get_serializer(
                obj,
                context={
                    'request': request,
                    'content_type': obj.content_type,
                    'object_id': obj.object_id,
                    'ttype': ttype,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


    # ---------- Update (partial) ----------
    @action(detail=False, methods=['patch'],
            url_path=r'update/(?P<ttype>audio|video|written)/(?P<slug>[-\w]+)')
    def update_for_type(self, request, ttype=None, slug=None):
        obj = self.get_queryset().filter(slug=slug, type=ttype).first()
        if not obj:
            raise NotFound("Not found")
        ser = self.get_serializer(obj, data=request.data, partial=True, context={'request': request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(self.get_serializer(obj, context={'request': request}).data)

    # ---------- Delete ----------
    @action(detail=False, methods=['delete'],
            url_path=r'delete/(?P<ttype>audio|video|written)/(?P<slug>[-\w]+)')
    def delete_for_type(self, request, ttype=None, slug=None):
        obj = self.get_queryset().filter(slug=slug, type=ttype).first()
        if not obj:
            raise NotFound("Not found")
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



# ----------------------------------------------
# 🏛️ TestimonyViewSet (Organization-scoped)
# ----------------------------------------------
class TestimonyViewSet(OrganizationActionMixin, viewsets.ModelViewSet):
    queryset = Testimony.objects.all()
    serializer_class = TestimonySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        # Check for organization and its subtypes (Church, MissionOrganization, etc.)
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Testimony.objects.none()

        # Check if organization is restricted, only members can view restricted testimonies
        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return Testimony.objects.none()  # If not a member of the organization, return empty queryset

        # Fetch testimonies related to the organization or its subtypes
        organization_content_type = ContentType.objects.get_for_model(Organization)
        sub_organizations = [
            Church, MissionOrganization, ChristianPublishingHouse, ChristianCounselingCenter,
            ChristianWorshipMinistry, ChristianConferenceCenter, ChristianEducationalInstitution,
            ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization
        ]
        for sub_org_model in sub_organizations:
            sub_org = sub_org_model.objects.filter(organization=organization).first()
            if sub_org:
                sub_org_content_type = ContentType.objects.get_for_model(sub_org_model)
                return queryset.filter(
                    Q(content_type=organization_content_type, object_id=organization.id) |
                    Q(content_type=sub_org_content_type, object_id=sub_org.id),
                    is_active=True, is_hidden=False
                ).distinct()

        # Default to returning testimonies for the main organization
        return queryset.filter(
            content_type=organization_content_type,
            object_id=organization.id,
            is_active=True,
            is_hidden=False
        ).distinct()

    def perform_create(self, serializer):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Check for sub-organization (Church, MissionOrganization, etc.)
        sub_organizations = [
            Church, MissionOrganization, ChristianPublishingHouse, ChristianCounselingCenter,
            ChristianWorshipMinistry, ChristianConferenceCenter, ChristianEducationalInstitution,
            ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization
        ]
        for sub_org_model in sub_organizations:
            sub_org = sub_org_model.objects.filter(organization=organization).first()
            if sub_org:
                content_type = ContentType.objects.get_for_model(sub_org_model)
                serializer.save(
                    content_type=content_type,
                    object_id=sub_org.id,
                    published_at=timezone.now(),
                    is_active=True
                )
                return

        # Default to saving for the main organization
        content_type = ContentType.objects.get_for_model(Organization)
        serializer.save(
            content_type=content_type,
            object_id=organization.id,
            published_at=timezone.now(),
            is_active=True
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to update this testimony"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this testimony"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Example action to fetch all testimonies for exploration
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_testimonies(self, request):
        testimonies = Testimony.objects.filter(is_active=True, is_hidden=False)
        serializer = self.get_serializer(testimonies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Search testimonies by title.
    @action(detail=False, methods=['get'], url_path='search', permission_classes=[IsAuthenticated])
    def search_testimonies(self, request):
        query = request.query_params.get('q', None)
        if query:
            testimonies = Testimony.objects.filter(title__icontains=query, is_active=True, is_hidden=False)
        else:
            testimonies = Testimony.objects.all()
        serializer = self.get_serializer(testimonies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


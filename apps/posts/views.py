from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.db import transaction, IntegrityError

from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import NotFound

from apps.posts.permissions import IsOwnerOfMemberTestimony
from apps.profiles.models import Friendship
from apps.profilesOrg.models import Organization
from .serializers import (
                    ReactionSerializer, CommentSerializer,
                    TestimonySerializer, WitnessSerializer, MomentSerializer, PraySerializer,
                    AnnouncementSerializer, ServiceEventSerializer, LessonSerializer, PreachSerializer,
                    WorshipSerializer, MediaContentSerializer,  LibrarySerializer, MissionSerializer, ConferenceSerializer, FutureConferenceSerializer
                )
from .models import (
                    Reaction, Comment,
                    Testimony, Witness, Moment, Pray,
                    Announcement, ServiceEvent, Lesson, Preach,
                    Worship, MediaContent, Library, Mission, Conference, FutureConference
                )
from apps.posts.mixins.mixins import (
                    ReactionMixin, CommentMixin,
                    MemberActionMixin, GuestUserActionMixin, OrganizationActionMixin, ResourceManagementMixin
                )
from apps.profilesOrg.models import (
                    Organization, Church, MissionOrganization, ChristianPublishingHouse, 
                    ChristianCounselingCenter, ChristianWorshipMinistry, ChristianConferenceCenter, ChristianEducationalInstitution, 
                    ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization
                )
from django.db import IntegrityError, DatabaseError

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# REACTIONS Viewset --------------------------------------------------------------------------
class ReactionViewSet(viewsets.ModelViewSet):
    queryset = Reaction.objects.all()
    serializer_class = ReactionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        content_type = self.request.query_params.get('content_type')
        object_id = self.request.query_params.get('object_id')
        if content_type and object_id:
            try:
                content_type_instance = ContentType.objects.get(model=content_type)
                return Reaction.objects.filter(
                    content_type=content_type_instance, object_id=object_id
                )
            except ContentType.DoesNotExist:
                return Reaction.objects.none()
        return super().get_queryset()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.name_id != request.user.id:
            return Response({"error": "You are not allowed to edit this reaction"}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.name_id != request.user.id:
            return Response({"error": "You are not allowed to delete this reaction"}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


# COMMENT & RE_COMMENT Viewset -----------------------------------------------------------------
class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        if content_type and object_id:
            try:
                content_type_model = ContentType.objects.get(model=content_type)
                comments = Comment.objects.filter(content_type=content_type_model, object_id=object_id)
            except ContentType.DoesNotExist:
                return Response({"error": "Invalid content type"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            comments = Comment.objects.none()
        serializer = self.get_serializer(comments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        content_type = request.data.get('content_type')
        object_id = request.data.get('object_id')
        if not content_type or not object_id:
            return Response({"error": "Content type and object ID are required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            content_type_model = ContentType.objects.get(model=content_type)
        except ContentType.DoesNotExist:
            return Response({"error": "Invalid content type"}, status=status.HTTP_400_BAD_REQUEST)
        request.data['content_type'] = content_type_model.id
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.name != request.user:
            return Response({"error": "You are not allowed to edit this comment"}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.name != request.user:
            return Response({"error": "You are not allowed to delete this comment"}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
# Me Testimony ViewSet -------------------------------------------------------------------
class MeTestimonyViewSet(ReactionMixin, CommentMixin, viewsets.GenericViewSet):
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
        return self._owner_qs(self.request)

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
        return Response(self.get_serializer(obj, context={"request": request}).data)

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

        return Response(self.get_serializer(obj, context={'request': request}).data, status=status.HTTP_201_CREATED)


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

    # ---------- Detail (optional) ----------
    @action(detail=False, methods=['get'], url_path=r'detail/(?P<slug>[-\w]+)')
    def detail(self, request, slug=None):
        obj = self.get_queryset().filter(slug=slug).first()
        if not obj:
            raise NotFound("Not found")
        return Response(self.get_serializer(obj, context={'request': request}).data)



# SERVICE EVENT ViewSet ---------------------------------------------------------------------------------------------------
class ServiceEventViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin):
    queryset = ServiceEvent.objects.all()
    serializer_class = ServiceEventSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        # Check for organization and its subtypes (Church, MissionOrganization, etc.)
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return ServiceEvent.objects.none()

        # Check if organization is restricted, only members can view restricted service events
        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return ServiceEvent.objects.none()  # If not a member of the organization, return empty queryset

        # Fetch service events related to the organization or its subtypes
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

        # Default to returning service events for the main organization
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
                    is_active=True
                )
                return

        # Default to saving for the main organization
        content_type = ContentType.objects.get_for_model(Organization)
        serializer.save(
            content_type=content_type,
            object_id=organization.id,
            is_active=True
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to update this service event"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save()

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this service event"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()


# TESTIMONY Viewset --------------------------------------------------------------------------
class TestimonyViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin):
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


# Witness ViewSet ---------------------------------------------------------------------------------------------------
class WitnessViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin):
    queryset = Witness.objects.all()
    serializer_class = WitnessSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Witness.objects.none()

        return queryset.filter(
            content_type=ContentType.objects.get_for_model(Organization),
            object_id=organization.id,
            is_active=True,
            is_hidden=False
        ).distinct()

    def perform_create(self, serializer):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer.save(
            content_type=ContentType.objects.get_for_model(organization),
            object_id=organization.id,
            re_published_at=timezone.now(),
            is_active=True
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to update this witness"}, status=status.HTTP_403_FORBIDDEN)
        
        serializer.save()

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this witness"}, status=status.HTTP_403_FORBIDDEN)
        
        instance.delete()

    # Action for retrieving related testimonies for the witness
    @action(detail=True, methods=['get'], url_path='testimonies', permission_classes=[IsAuthenticated])
    def get_testimonies(self, request, slug=None):
        witness = self.get_object()
        testimonies = witness.testimony.all()  # Retrieve related testimonies
        return Response({
            "witness": witness.title,
            "testimonies": [str(testimony) for testimony in testimonies]
        }, status=status.HTTP_200_OK)


# Moment ViewSet ---------------------------------------------------------------------------------------------------
class MomentViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, MemberActionMixin, GuestUserActionMixin, OrganizationActionMixin):
    queryset = Moment.objects.all()
    serializer_class = MomentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_object(self):
        slug = self.kwargs.get('slug')
        return Moment.objects.get(slug=slug)

    def get_queryset(self):
        queryset = super().get_queryset()
        
        if not self.request.user.is_authenticated:
            return queryset.filter(is_active=True, is_hidden=False, is_restricted=False)
        
        if self.request.user.is_staff:
            return queryset

        queryset = queryset.filter(is_active=True, is_hidden=False)

        # Fetch ContentType for Member, GuestUser, and Organization models
        member_user = getattr(self.request.user, 'member', None)
        guest_user = getattr(self.request.user, 'guestuser', None)
        organization_slug = self.kwargs.get('slug')

        if member_user:
            member_content_type = ContentType.objects.get_for_model(self.request.user.member)
            organization_memberships = member_user.organization_memberships.all() if member_user else []
            if not organization_memberships.exists():
                organization_memberships = []  # If no memberships, return an empty queryset
            friends = Friendship.objects.filter(
                Q(from_user_id=self.request.user.id) |
                Q(to_user_id=self.request.user.id),
                status='accepted'
            ).values_list('from_user__username', 'to_user__username')

            organization_content_type = ContentType.objects.get_for_model('profilesOrg.Organization')
            queryset = queryset.filter(
                Q(content_type=member_content_type, object_id__in=friends) |
                Q(content_type=organization_content_type, object_id__in=organization_memberships.values_list('id', flat=True)) |
                Q(is_restricted=False)
            ).distinct()

        elif guest_user:
            guestuser_content_type = ContentType.objects.get_for_model(self.request.user.guestuser)
            queryset = queryset.filter(
                Q(content_type=guestuser_content_type, object_id=guest_user.id) |
                Q(is_restricted=False)
            ).distinct()

        if organization_slug:
            organization_content_type = ContentType.objects.get_for_model('profilesOrg.Organization')
            organization = Organization.objects.filter(slug=organization_slug).first()
            if organization:
                queryset = queryset.filter(
                    Q(content_type=organization_content_type, object_id=organization.id) |
                    Q(is_restricted=False)
                ).distinct()

        return queryset

    def perform_create(self, serializer):
        serializer.save(published_at=timezone.now(), is_active=True)

    def perform_update(self, request, serializer):
        instance = self.get_object()
        if instance.author != request.user:
            return Response({"error": "You are not allowed to update this Moment"}, status=status.HTTP_403_FORBIDDEN)
        instance = serializer.save(updated_at=timezone.now())
        return instance

    def perform_destroy(self, request, instance):
        if instance.author != request.user:
            return Response({"error": "You are not allowed to delete this Moment"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Retrieve all Moments for exploration.
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_moments(self, request):
        moments = Moment.objects.filter(is_active=True, is_hidden=False)
        serializer = self.get_serializer(moments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Search Moment by content or title (if applicable).
    @action(detail=False, methods=['get'], url_path='search', permission_classes=[IsAuthenticated])
    def search_moments(self, request):
        query = request.query_params.get('q', None)
        if query:
            moments = Moment.objects.filter(content__icontains=query, is_active=True, is_hidden=False)
        else:
            moments = Moment.objects.all()
        serializer = self.get_serializer(moments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



# Pray ViewSet ---------------------------------------------------------------------------------------------------
class PrayViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, MemberActionMixin):
    queryset = Pray.objects.all()
    serializer_class = PraySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return queryset.filter(is_active=True, is_hidden=False, is_restricted=False)
        
        member_user = getattr(self.request.user, 'member', None)

        if member_user:
            # Filter only active prays that are visible to members
            queryset = queryset.filter(
                content_type=ContentType.objects.get_for_model(member_user),
                object_id=member_user.id,
                is_active=True,
                is_hidden=False
            ).distinct()
        else:
            return Pray.objects.none()  # If not a member, return no results
        return queryset

    def perform_create(self, serializer):
        member = self.request.user.member
        serializer.save(
            content_type=ContentType.objects.get_for_model(member),
            object_id=member.id,
            published_at=timezone.now(),
            is_active=True
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.content_object != self.request.user.member:
            return Response({"error": "You are not allowed to update this pray"}, status=status.HTTP_403_FORBIDDEN)
        instance = serializer.save(updated_at=timezone.now())
        return instance

    def perform_destroy(self, instance):
        if instance.content_object != self.request.user.member:
            return Response({"error": "You are not allowed to delete this pray"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Retrieve all active and visible prays for exploration
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_prays(self, request):
        prays = Pray.objects.filter(is_active=True, is_hidden=False, is_restricted=False)
        serializer = PraySerializer(prays, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Announcement ViewSet ---------------------------------------------------------------------------------------------------
class AnnouncementViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin):
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Announcement.objects.none()  # If the organization doesn't exist, return an empty queryset

        return queryset.filter(
            content_type=ContentType.objects.get_for_model(Organization),
            object_id=organization.id,
            is_active=True,
            is_hidden=False
        ).distinct()

    def perform_create(self, serializer):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer.save(
            content_type=ContentType.objects.get_for_model(organization),
            object_id=organization.id,
            created_at=timezone.now(),
            is_active=True
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to update this announcement"}, status=status.HTTP_403_FORBIDDEN)
        
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this announcement"}, status=status.HTTP_403_FORBIDDEN)
        
        instance.delete()


# LESSON ViewSet -----------------------------------------------------------------------------------------------------
class LessonViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        # Check for organization and its subtypes (Church, MissionOrganization, etc.)
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Lesson.objects.none()

        # Check if organization is restricted, only members can view restricted lessons
        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return Lesson.objects.none()  # If not a member of the organization, return empty queryset

        # Fetch lessons related to the organization or its subtypes
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

        # Default to returning lessons for the main organization
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
            return Response({"error": "You are not allowed to update this lesson"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this lesson"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Explore Lessons
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_lessons(self, request):
        lessons = Lesson.objects.filter(is_active=True, is_hidden=False)
        serializer = self.get_serializer(lessons, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Search Lessons by title or description
    @action(detail=False, methods=['get'], url_path='search', permission_classes=[IsAuthenticated])
    def search_lessons(self, request):
        query = request.query_params.get('q', None)
        if query:
            lessons = Lesson.objects.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query),
                is_active=True, is_hidden=False
            )
        else:
            lessons = Lesson.objects.filter(is_active=True, is_hidden=False)
        
        serializer = self.get_serializer(lessons, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



# Preach ViewSet ---------------------------------------------------------------------------------------------------
class PreachViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin):
    queryset = Preach.objects.all()
    serializer_class = PreachSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        # Check for organization and its subtypes (Church, MissionOrganization, etc.)
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Preach.objects.none()

        # Check if organization is restricted, only members can view restricted preaches
        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return Preach.objects.none()  # If not a member of the organization, return empty queryset

        # Fetch preaches related to the organization or its subtypes
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

        # Default to returning preaches for the main organization
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
            return Response({"error": "You are not allowed to update this preach"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this preach"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Explore Preaches
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_preaches(self, request):
        preaches = Preach.objects.filter(is_active=True, is_hidden=False)
        serializer = self.get_serializer(preaches, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Search Preaches by title
    @action(detail=False, methods=['get'], url_path='search', permission_classes=[IsAuthenticated])
    def search_preaches(self, request):
        query = request.query_params.get('q', None)
        if query:
            preaches = Preach.objects.filter(
                Q(title__icontains=query),
                is_active=True, is_hidden=False
            )
        else:
            preaches = Preach.objects.filter(is_active=True, is_hidden=False)
        
        serializer = self.get_serializer(preaches, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Worship ViewSet ---------------------------------------------------------------------------------------------------
class WorshipViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin, ResourceManagementMixin):
    queryset = Worship.objects.all()
    serializer_class = WorshipSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        # Check for organization and its subtypes (Church, MissionOrganization, etc.)
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Worship.objects.none()

        # Check if organization is restricted, only members can view restricted worships
        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return Worship.objects.none()  # If not a member of the organization, return empty queryset

        # Fetch worships related to the organization or its subtypes
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

        # Default to returning worships for the main organization
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
            return Response({"error": "You are not allowed to update this worship"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this worship"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Explore Worships
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_worships(self, request):
        worships = Worship.objects.filter(is_active=True, is_hidden=False)
        serializer = self.get_serializer(worships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Search Worships by title or sermon
    @action(detail=False, methods=['get'], url_path='search', permission_classes=[IsAuthenticated])
    def search_worships(self, request):
        query = request.query_params.get('q', None)
        if query:
            worships = Worship.objects.filter(
                Q(title__icontains=query) |
                Q(sermon__icontains=query),
                is_active=True, is_hidden=False
            )
        else:
            worships = Worship.objects.filter(is_active=True, is_hidden=False)
        
        serializer = self.get_serializer(worships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Media Content ViewSet ---------------------------------------------------------------------------------------------------
class MediaContentViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin):
    queryset = MediaContent.objects.all()
    serializer_class = MediaContentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        # Check for organization and its subtypes (Church, MissionOrganization, etc.)
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return MediaContent.objects.none()

        # Check if organization is restricted, only members can view restricted media contents
        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return MediaContent.objects.none()  # If not a member of the organization, return empty queryset

        # Fetch media contents related to the organization or its subtypes
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

        # Default to returning media contents for the main organization
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
            return Response({"error": "You are not allowed to update this media content"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this media content"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Explore Media Contents
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_media_contents(self, request):
        media_contents = MediaContent.objects.filter(is_active=True, is_hidden=False)
        serializer = self.get_serializer(media_contents, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Search Media Contents by title or description
    @action(detail=False, methods=['get'], url_path='search', permission_classes=[IsAuthenticated])
    def search_media_contents(self, request):
        query = request.query_params.get('q', None)
        if query:
            media_contents = MediaContent.objects.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query),
                is_active=True, is_hidden=False
            )
        else:
            media_contents = MediaContent.objects.filter(is_active=True, is_hidden=False)
        
        serializer = self.get_serializer(media_contents, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Library ViewSet ---------------------------------------------------------------------------------------------------
class LibraryViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin):
    queryset = Library.objects.all()
    serializer_class = LibrarySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        # Check for organization and its subtypes (Church, MissionOrganization, etc.)
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Library.objects.none()

        # Check if organization is restricted, only members can view restricted libraries
        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return Library.objects.none()  # If not a member of the organization, return empty queryset

        # Fetch libraries related to the organization or its subtypes
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

        # Default to returning libraries for the main organization
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
                    published_date=timezone.now(),
                    is_active=True
                )
                return

        # Default to saving for the main organization
        content_type = ContentType.objects.get_for_model(Organization)
        serializer.save(
            content_type=content_type,
            object_id=organization.id,
            published_date=timezone.now(),
            is_active=True
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to update this library content"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this library content"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Explore Libraries
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_libraries(self, request):
        libraries = Library.objects.filter(is_active=True, is_hidden=False)
        serializer = self.get_serializer(libraries, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Search Libraries by title or author
    @action(detail=False, methods=['get'], url_path='search', permission_classes=[IsAuthenticated])
    def search_libraries(self, request):
        query = request.query_params.get('q', None)
        if query:
            libraries = Library.objects.filter(
                Q(book_name__icontains=query) |
                Q(author__icontains=query),
                is_active=True, is_hidden=False
            )
        else:
            libraries = Library.objects.filter(is_active=True, is_hidden=False)
        
        serializer = self.get_serializer(libraries, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Mission ViewSet ---------------------------------------------------------------------------------------------------
class MissionViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin):
    queryset = Mission.objects.all()
    serializer_class = MissionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        # Check for organization and its subtypes (Church, MissionOrganization, etc.)
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Mission.objects.none()

        # Check if organization is restricted, only members can view restricted missions
        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return Mission.objects.none()  # If not a member of the organization, return empty queryset

        # Fetch missions related to the organization or its subtypes
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

        # Default to returning missions for the main organization
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
            return Response({"error": "You are not allowed to update this mission"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this mission"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Explore Missions
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_missions(self, request):
        missions = Mission.objects.filter(is_active=True, is_hidden=False)
        serializer = self.get_serializer(missions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Search Missions by name or description
    @action(detail=False, methods=['get'], url_path='search', permission_classes=[IsAuthenticated])
    def search_missions(self, request):
        query = request.query_params.get('q', None)
        if query:
            missions = Mission.objects.filter(
                Q(mission_name__icontains=query) |
                Q(description__icontains=query),
                is_active=True, is_hidden=False
            )
        else:
            missions = Mission.objects.filter(is_active=True, is_hidden=False)
        
        serializer = self.get_serializer(missions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Conference ViewSet ---------------------------------------------------------------------------------------------------
class ConferenceViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin, ResourceManagementMixin):
    queryset = Conference.objects.all()
    serializer_class = ConferenceSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        # Check for organization and its subtypes (Church, etc.)
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Conference.objects.none()

        # Check if organization is restricted, only members can view restricted conferences
        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return Conference.objects.none()

        # Fetch conferences related to the organization or its subtypes
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

        # Default to returning conferences for the main organization
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
        
        # Check for sub-organization (Church, etc.)
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
            return Response({"error": "You are not allowed to update this conference"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this conference"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Workshop Lesson Actions for Conference
    @action(detail=True, methods=['get'], url_path='lessons', permission_classes=[IsAuthenticated])
    def get_lessons(self, request, slug=None):
        conference = self.get_object()
        lessons = conference.workshops.all()
        serializer = LessonSerializer(lessons, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='add-workshop', permission_classes=[IsAuthenticated])
    def add_workshop(self, request, slug=None):
        conference = self.get_object()
        lesson_id = request.data.get('lesson_id')
        if conference.content_object != request.user:
            return Response({"error": "You are not allowed to add a workshop to this conference"}, status=status.HTTP_403_FORBIDDEN)
        try:
            lesson = Lesson.objects.get(id=lesson_id)
            conference.workshops.add(lesson)
            return Response({"message": "Lesson added successfully"}, status=status.HTTP_201_CREATED)
        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='remove-workshop', permission_classes=[IsAuthenticated])
    def remove_workshop(self, request, slug=None):
        conference = self.get_object()
        lesson_id = request.data.get('lesson_id')
        try:
            lesson = Lesson.objects.get(id=lesson_id)
            conference.workshops.remove(lesson)
            return Response({"message": "Lesson removed successfully"}, status=status.HTTP_204_NO_CONTENT)
        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='edit-workshop', permission_classes=[IsAuthenticated])
    def edit_workshop(self, request, slug=None):
        lesson_id = request.data.get('lesson_id')
        try:
            lesson = Lesson.objects.get(id=lesson_id)
            serializer = LessonSerializer(lesson, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)


# Future Conference ViewSet ---------------------------------------------------------------------------------------------------
class FutureConferenceViewSet(viewsets.ModelViewSet, CommentMixin, ReactionMixin, OrganizationActionMixin):
    queryset = FutureConference.objects.all()
    serializer_class = FutureConferenceSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return FutureConference.objects.none()

        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return FutureConference.objects.none()

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
            return Response({"error": "You are not allowed to update this future conference"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this future conference"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Explore Future Conferences
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_future_conferences(self, request):
        future_conferences = FutureConference.objects.filter(is_active=True, is_hidden=False)
        serializer = self.get_serializer(future_conferences, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Search Future Conferences by name or description
    @action(detail=False, methods=['get'], url_path='search', permission_classes=[IsAuthenticated])
    def search_future_conferences(self, request):
        query = request.query_params.get('q', None)
        if query:
            future_conferences = FutureConference.objects.filter(
                Q(conference_name__icontains=query) |
                Q(conference_description__icontains=query),
                is_active=True, is_hidden=False
            )
        else:
            future_conferences = FutureConference.objects.filter(is_active=True, is_hidden=False)
        
        serializer = self.get_serializer(future_conferences, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

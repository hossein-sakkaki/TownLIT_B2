# apps/posts/views/missions.py
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status, viewsets

from apps.posts.models import Moment
from apps.posts.serializers.moments import MomentSerializer
from apps.posts.mixins.mixins import CommentMixin, OrganizationActionMixin
from apps.profilesOrg.models import Organization
from apps.posts.mixins.mixins import MemberActionMixin, GuestUserActionMixin


# Moment ViewSet ---------------------------------------------------------------------------------------------------
class MomentViewSet(viewsets.ModelViewSet, CommentMixin, MemberActionMixin, GuestUserActionMixin, OrganizationActionMixin):
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





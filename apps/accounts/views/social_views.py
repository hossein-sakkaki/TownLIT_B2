

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated    
from django.contrib.contenttypes.models import ContentType

from apps.accounts.models.social import SocialMediaLink, SocialMediaType
from apps.accounts.serializers.social_serializers import SocialMediaLinkSerializer, SocialMediaLinkReadOnlySerializer, SocialMediaTypeSerializer
from apps.profilesOrg.models import Organization
import utils as utils
import logging
from django.contrib.auth import get_user_model

CustomUser = get_user_model()
logger = logging.getLogger(__name__)





# Social Media Links ViewSet ------------------------------------------------------------------------------------
class SocialLinksViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
        
    @action(detail=False, methods=['get'], url_path='list', permission_classes=[IsAuthenticated])
    def list_links(self, request):
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
                
        if not content_type or not object_id:
            return Response({"error": "content_type and object_id are required."}, status=400)

        try:
            links = SocialMediaLink.objects.filter(content_type__model=content_type, object_id=object_id)
            
            if content_type == "customuser" and int(object_id) != request.user.id:
                return Response({"error": "Access denied to this user's links."}, status=403)
            elif content_type == "organization":
                organization = Organization.objects.filter(id=object_id, org_owners=request.user).first()
                if not organization:
                    return Response({"error": "Access denied to this organization's links."}, status=403)

            serializer = SocialMediaLinkReadOnlySerializer(links, many=True, context={'request': request})
            return Response({"links": serializer.data, "message": "Links fetched successfully."}, status=status.HTTP_200_OK)

        except (ValueError, TypeError):
            return Response({"error": "Invalid object ID or content_type."}, status=400)


    @action(detail=False, methods=['post'], url_path='add', permission_classes=[IsAuthenticated])
    def add_link(self, request):
        content_type = request.data.get('content_type')
        object_id = request.data.get('object_id')
        social_media_type = request.data.get('social_media_type')
        link = request.data.get('link')

        if not all([content_type, object_id, social_media_type, link]):
            return Response({"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if content_type == "customuser":
                if int(object_id) != request.user.id:
                    return Response({"error": "You cannot add links to this user."}, status=status.HTTP_403_FORBIDDEN)
                content_object = request.user
            elif content_type == "organization":
                organization = Organization.objects.filter(id=object_id, org_owners=request.user).first()
                if not organization:
                    return Response({"error": "You cannot add links to this organization."}, status=status.HTTP_403_FORBIDDEN)
                content_object = organization
            else:
                return Response({"error": "Invalid content_type provided."}, status=status.HTTP_400_BAD_REQUEST)

            serializer = SocialMediaLinkSerializer(
                data={
                    'social_media_type': social_media_type,
                    'link': link,
                    'content_type': content_type,
                    'object_id': object_id,
                },
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(content_object=content_object)
            return Response({"data": serializer.data, "message": "Social media link added successfully."}, status=status.HTTP_201_CREATED)

        except (ValueError, TypeError):
            return Response({"error": "Invalid object ID or content_type."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['delete'], url_path='delete', permission_classes=[IsAuthenticated])
    def delete_link(self, request):
        link_id = request.query_params.get('id')
        
        if not link_id:
            return Response({"error": "Link ID is required for deletion."}, status=400)

        try:
            link_id = int(link_id)
        except ValueError:
            return Response({"error": "Invalid Link ID."}, status=400)

        try:
            link = SocialMediaLink.objects.get(id=link_id)
            if isinstance(link.content_object, Organization):
                organization = Organization.objects.filter(id=link.content_object.id, org_owners=request.user).first()
                if not organization:
                    return Response({"error": "You cannot delete this link."}, status=403)
            elif link.content_object != request.user:
                return Response({"error": "You cannot delete this link."}, status=403)
            link.delete()
            return Response({"success": True, "message": "Link deleted successfully."}, status=status.HTTP_200_OK)

        except SocialMediaLink.DoesNotExist:
            return Response({"error": "Link not found."}, status=404)

    @action(detail=False, methods=['get'], url_path='social-media-types', permission_classes=[IsAuthenticated])
    def get_social_media_types(self, request):
        try:
            used_social_media = SocialMediaLink.objects.filter(
                content_type=ContentType.objects.get_for_model(request.user.__class__),
                object_id=request.user.id
            ).values_list('social_media_type', flat=True)
            available_types = SocialMediaType.objects.filter(is_active=True).exclude(id__in=used_social_media)
            serializer = SocialMediaTypeSerializer(available_types, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": "Failed to fetch social media types."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

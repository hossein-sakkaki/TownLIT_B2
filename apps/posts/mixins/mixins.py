from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.posts.models import (
                    Reaction, Comment, Resource,
                )
from apps.posts.serializers import (
                    ReactionSerializer, CommentSerializer, ResourceSerializer,
                )
from apps.profilesOrg.models import Organization
from apps.main.permissions import IsFullAccessAdmin, IsLimitedAccessAdmin



# REACTIONS Mixin ----------------------------------------------------------------------------
class ReactionMixin:
    # Mixin for handling reactions related to any model with GenericForeignKey.        
    @action(detail=True, methods=['get', 'post'], url_path='reactions', permission_classes=[IsAuthenticated])
    def reactions(self, request, slug=None):
        instance = self.get_object()
        try:
            content_type = ContentType.objects.get_for_model(instance)
        except ContentType.DoesNotExist:
            return Response({"error": "Invalid content type"}, status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'GET':
            # Retrieve all reactions for this object
            reactions = Reaction.objects.filter(content_type=content_type, object_id=instance.id)
            serializer = ReactionSerializer(reactions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        if request.method == 'POST':
            # Check if the reaction already exists for the current user
            existing_reaction = Reaction.objects.filter(
                content_type=content_type, object_id=instance.id, name=request.user
            ).first()
            if existing_reaction:
                return Response({"error": "You have already reacted to this content."}, status=status.HTTP_400_BAD_REQUEST)

            # Add a new reaction to this object
            serializer = ReactionSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    serializer.save(content_type=content_type, object_id=instance.id)
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                except Exception as e:
                    return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)        
        
    @action(detail=True, methods=['delete'], url_path='remove-reaction', permission_classes=[IsAuthenticated])
    def remove_reaction(self, request, slug=None):
        instance = self.get_object()
        try:
            content_type = ContentType.objects.get_for_model(instance)
        except ContentType.DoesNotExist:
            return Response({"error": "Invalid content type"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            reaction = Reaction.objects.get(content_type=content_type, object_id=instance.id, name=request.user)
            reaction.delete()
            return Response({"message": "Reaction removed successfully"}, status=status.HTTP_204_NO_CONTENT)
        except Reaction.DoesNotExist:
            return Response({"error": "Reaction not found or you don't have permission to remove it"}, status=status.HTTP_404_NOT_FOUND)


# COMMENT Mixin -------------------------------------------------------------------------------
class CommentMixin:
    # Mixin for handling comments related to any model with GenericForeignKey.
    @action(detail=True, methods=['get', 'post'], url_path='comments', permission_classes=[IsAuthenticated])
    def comments(self, request, slug=None):
        instance = self.get_object()
        try:
            content_type = ContentType.objects.get_for_model(instance)
        except ContentType.DoesNotExist:
            return Response({"error": "Invalid content type"}, status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'GET':
            # Retrieve all comments for this object
            comments = Comment.objects.filter(content_type=content_type, object_id=instance.id)
            serializer = CommentSerializer(comments, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        if request.method == 'POST':
            # Add a new comment for this object
            serializer = CommentSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    serializer.save(content_type=content_type, object_id=instance.id)
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                except Exception as e:
                    return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='update-comment', permission_classes=[IsAuthenticated])
    def update_comment(self, request, slug=None):
        instance = self.get_object()
        content_type = ContentType.objects.get_for_model(instance)
        try:
            comment = Comment.objects.get(content_type=content_type, object_id=instance.id, name=request.user)
            serializer = CommentSerializer(comment, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Comment.DoesNotExist:
            return Response({"error": "Comment not found or you don't have permission to update it"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['delete'], url_path='delete-comment', permission_classes=[IsAuthenticated])
    def delete_comment(self, request, slug=None):
        instance = self.get_object()
        content_type = ContentType.objects.get_for_model(instance)
        try:
            comment = Comment.objects.get(content_type=content_type, object_id=instance.id, name=request.user)
            comment.delete()
            return Response({"message": "Comment deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
        except Comment.DoesNotExist:
            return Response({"error": "Comment not found or you don't have permission to delete it"}, status=status.HTTP_404_NOT_FOUND)


# MEMBER ACTION Mixin ----------------------------------------------------------------------------
class MemberActionMixin:
    # Mixin for managing actions like adding, updating, and deleting resources for members.
    @action(detail=False, methods=['post'], url_path='add-member-item', permission_classes=[IsAuthenticated])
    def add_member_item(self, request):
        member = request.user.member
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            item = serializer.save()
            # Using GenericForeignKey to link the content properly
            content_type = ContentType.objects.get_for_model(member)
            item.content_type = content_type  # Set the content type for the item
            item.object_id = member.id  # Set the object_id for the member
            item.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='update-member-item', permission_classes=[IsAuthenticated])
    def update_member_item(self, request, slug=None):
        try:
            item = self.get_object()
            member = request.user.member
            # Check if the item belongs to the member using content_type and object_id
            if item.content_type == ContentType.objects.get_for_model(member) and item.object_id == member.id:
                serializer = self.get_serializer(item, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save(updated_at=timezone.now())
                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": f"You are not authorized to update this {self.model_name}"}, status=status.HTTP_403_FORBIDDEN)
        except self.queryset.model.DoesNotExist:
            return Response({"error": f"{self.model_name} not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['delete'], url_path='delete-member-item', permission_classes=[IsAuthenticated])
    def delete_member_item(self, request, slug=None):
        try:
            item = self.get_object()
            member = request.user.member
            # Check if the item belongs to the member using content_type and object_id
            if item.content_type == ContentType.objects.get_for_model(member) and item.object_id == member.id:
                item.delete()
                return Response({"message": f"{self.model_name} deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
            return Response({"error": f"You are not authorized to delete this {self.model_name}"}, status=status.HTTP_403_FORBIDDEN)
        except self.queryset.model.DoesNotExist:
            return Response({"error": f"{self.model_name} not found"}, status=status.HTTP_404_NOT_FOUND)


# GUESTUSER ACTION Mixin ----------------------------------------------------------------------------
class GuestUserActionMixin:
    # Mixin for managing actions like adding, updating, and deleting resources for guest users.
    @action(detail=False, methods=['post'], url_path='add-guestuser-item', permission_classes=[IsAuthenticated])
    def add_guestuser_item(self, request):
        guest_user = request.user.guestuser
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            item = serializer.save()
            # Link the guest user with the item using GenericForeignKey
            content_type = ContentType.objects.get_for_model(guest_user)
            item.content_type = content_type  # Set the content type for the item
            item.object_id = guest_user.id  # Set the object_id for the guest_user
            item.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='update-guestuser-item', permission_classes=[IsAuthenticated])
    def update_guestuser_item(self, request, slug=None):
        try:
            item = self.get_object()
            guest_user = request.user.guestuser
            # Check if the item belongs to the guest user using content_type and object_id
            if item.content_type == ContentType.objects.get_for_model(guest_user) and item.object_id == guest_user.id:
                serializer = self.get_serializer(item, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save(updated_at=timezone.now())
                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": f"You are not authorized to update this {self.model_name}"}, status=status.HTTP_403_FORBIDDEN)
        except self.queryset.model.DoesNotExist:
            return Response({"error": f"{self.model_name} not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['delete'], url_path='delete-guestuser-item', permission_classes=[IsAuthenticated])
    def delete_guestuser_item(self, request, slug=None):
        try:
            item = self.get_object()
            guest_user = request.user.guestuser
            # Check if the item belongs to the guest user using content_type and object_id
            if item.content_type == ContentType.objects.get_for_model(guest_user) and item.object_id == guest_user.id:
                item.delete()
                return Response({"message": f"{self.model_name} deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
            return Response({"error": f"You are not authorized to delete this {self.model_name}"}, status=status.HTTP_403_FORBIDDEN)
        except self.queryset.model.DoesNotExist:
            return Response({"error": f"{self.model_name} not found"}, status=status.HTTP_404_NOT_FOUND)



# ORGANIZATION ACTION Mixin -------------------------------------------------------------------------
class OrganizationActionMixin:
    # Mixin for managing actions like adding, updating, and deleting resources for organizations.
    @action(detail=False, methods=['post'], url_path='add-organization-item', permission_classes=[IsFullAccessAdmin, IsLimitedAccessAdmin])
    def add_organization_item(self, request):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()  # Get organization by slug
        if not organization:
            return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            item = serializer.save()
            # Linking the item with organization using GenericForeignKey
            content_type = ContentType.objects.get_for_model(organization)
            item.content_type = content_type
            item.object_id = organization.id
            item.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='update-organization-item', permission_classes=[IsFullAccessAdmin, IsLimitedAccessAdmin])
    def update_organization_item(self, request, slug=None):
        try:
            item = self.get_object()
            organization_slug = self.kwargs.get('slug')
            organization = Organization.objects.filter(slug=organization_slug).first()  # Get organization by slug
            if not organization:
                return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)

            # Check if the item belongs to the organization
            if item.content_type == ContentType.objects.get_for_model(organization) and item.object_id == organization.id:
                serializer = self.get_serializer(item, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save(updated_at=timezone.now())
                    return Response(serializer.data, status=status.HTTP_200_OK)
            return Response({"error": f"You are not authorized to update this {self.model_name}"}, status=status.HTTP_403_FORBIDDEN)
        except self.queryset.model.DoesNotExist:
            return Response({"error": f"{self.model_name} not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['delete'], url_path='delete-organization-item', permission_classes=[IsFullAccessAdmin, IsLimitedAccessAdmin])
    def delete_organization_item(self, request, slug=None):
        try:
            item = self.get_object()
            organization_slug = self.kwargs.get('slug')
            organization = Organization.objects.filter(slug=organization_slug).first()  # Get organization by slug
            if not organization:
                return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
            
            # Check if the item belongs to the organization
            if item.content_type == ContentType.objects.get_for_model(organization) and item.object_id == organization.id:
                item.delete()
                return Response({"message": f"{self.model_name} deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
            return Response({"error": f"You are not authorized to delete this {self.model_name}"}, status=status.HTTP_403_FORBIDDEN)
        except self.queryset.model.DoesNotExist:
            return Response({"error": f"{self.model_name} not found"}, status=status.HTTP_404_NOT_FOUND)



# RESOURCE MANAGEMENT Mixin -------------------------------------------------------------------------------
class ResourceManagementMixin:    
    def get_resource_field(self, parent):
        if hasattr(parent, 'get_resource_field_name'):
            resource_field_name = parent.get_resource_field_name()
        else:
            resource_field_name = 'resources'
        resource_field = getattr(parent, resource_field_name, None)
        if resource_field is None:
            raise AttributeError(f"Resource field '{resource_field_name}' not found in the model {parent.__class__.__name__}")
        return resource_field

    @action(detail=True, methods=['post'], url_path='add-resource', permission_classes=[IsAuthenticated])
    def add_resource(self, request, pk=None):
        parent = self.get_object()  # The parent object (e.g. Conference, Lesson, etc.)
        serializer = ResourceSerializer(data=request.data)
        if serializer.is_valid():
            resource = serializer.save()
            resource_field = self.get_resource_field(parent)
            resource_field.add(resource)  # Adding resource to the parent model
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='update-resource', permission_classes=[IsAuthenticated])
    def update_resource(self, request, pk=None):
        parent = self.get_object()
        resource_id = request.data.get('resource_id')
        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response({"error": "Resource not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ResourceSerializer(resource, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='delete-resource', permission_classes=[IsAuthenticated])
    def delete_resource(self, request, pk=None):
        parent = self.get_object()
        resource_id = request.data.get('resource_id')
        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response({"error": "Resource not found"}, status=status.HTTP_404_NOT_FOUND)
        resource_field = self.get_resource_field(parent)
        resource_field.remove(resource)
        resource.delete()
        return Response({"message": "Resource deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
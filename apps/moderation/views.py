from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from .models import CollaborationRequest, JobApplication, AccessRequest, ReviewLog
from .utils import create_review_log
from .serializers import (
    CollaborationRequestSerializer,
    JobApplicationSerializer,
    ReviewLogSerializer,
    AccessRequestSerializer
)
from common.permissions import IsAdminOrReadOnly



# CollaborationRequest ViewSet ----------------------------------------------------------
class CollaborationRequestViewSet(viewsets.ModelViewSet):
    queryset = CollaborationRequest.objects.all().order_by('-submitted_at')
    serializer_class = CollaborationRequestSerializer
    permission_classes = [IsAdminOrReadOnly]

    @method_decorator(ratelimit(key='user_or_ip', rate='5/m', method='POST', block=True))
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        # Check spam field before validation
        company_name = request.data.get("company_name", "")
        if company_name.strip():
            raise serializers.ValidationError("Spam detected.")

        try:
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            return Response({
                "message": "Thank you for your willingness to collaborate. Our team will prayerfully review your request and contact you if needed.",
                "data": self.get_serializer(instance).data
            }, status=status.HTTP_201_CREATED)

        except ValidationError as ve:
            return Response({
                "error": "Your submission contains errors.",
                "details": ve.detail
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "An unexpected error occurred. Please try again later.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            

    def perform_update(self, serializer):
        instance = serializer.save(last_reviewed_by=self.request.user)

        # Log only if changed by staff
        if self.request.user.is_staff:
            create_review_log(
                admin_user=self.request.user,
                target_instance=instance,
                action_text=f"Updated collaboration status to '{instance.status}'",
                comment=instance.admin_comment or instance.admin_note or ""
            )


# JobApplication ViewSet ---------------------------------------------------------- 
class JobApplicationViewSet(viewsets.ModelViewSet):
    queryset = JobApplication.objects.all().order_by('-submitted_at')
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAdminOrReadOnly]

    @method_decorator(ratelimit(key='user_or_ip', rate='5/m', method='POST', block=True))
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        # Check spam field before validation
        company_name = request.data.get("company_name", "")
        if company_name.strip():
            raise serializers.ValidationError("Spam detected.")

        try:
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            return Response({
                "message": "Your application was received. Our team will prayerfully review it and contact you if appropriate.",
                "data": self.get_serializer(instance).data
            }, status=status.HTTP_201_CREATED)

        except ValidationError as ve:
            return Response({
                "error": "Your submission contains errors.",
                "details": ve.detail
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "An unexpected error occurred. Please try again later.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def perform_update(self, serializer):
        instance = serializer.save(last_reviewed_by=self.request.user)

        if self.request.user.is_staff:
            create_review_log(
                admin_user=self.request.user,
                target_instance=instance,
                action_text=f"Job application status changed to '{instance.status}'",
                comment=instance.admin_comment or instance.admin_note or ""
            )

# Access Request ViewSet ---------------------------------------------------------------
class AccessRequestViewSet(viewsets.ModelViewSet):
    queryset = AccessRequest.objects.all().order_by("-submitted_at")
    serializer_class = AccessRequestSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return AccessRequest.objects.none()

    def perform_create(self, serializer):
        serializer.save()
        

# ReviewLog Read-only ViewSet ----------------------------------------------------------
class ReviewLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReviewLog.objects.all().order_by('-created_at')
    serializer_class = ReviewLogSerializer
    permission_classes = [permissions.IsAdminUser]

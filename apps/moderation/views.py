from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from .models import CollaborationRequest, JobApplication, ReviewLog
from .serializers import (
    CollaborationRequestSerializer,
    JobApplicationSerializer,
    ReviewLogSerializer,
)
from common.permissions import IsAdminOrReadOnly
from .constants import (
    COLLABORATION_STATUS_REVIEWED,
    COLLABORATION_STATUS_CONTACTED,
    COLLABORATION_STATUS_CLOSED,
    JOB_STATUS_REVIEWED,
    JOB_STATUS_INTERVIEW,
    JOB_STATUS_HIRED,
    JOB_STATUS_REJECTED
)



# -----------------------------
# CollaborationRequest ViewSet
# -----------------------------
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
            instance = serializer.save(
                user=request.user if request.user.is_authenticated else None
            )
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

        ReviewLog.objects.create(
            admin=self.request.user,
            action=f"Collaboration status changed to {instance.status}",
            comment=instance.admin_comment or "",
            target=instance
        )


# -----------------------------
# JobApplication ViewSet
# -----------------------------
class JobApplicationViewSet(viewsets.ModelViewSet):
    queryset = JobApplication.objects.all().order_by('-submitted_at')
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user if self.request.user.is_authenticated else None)

    def perform_update(self, serializer):
        instance = serializer.save(last_reviewed_by=self.request.user)

        ReviewLog.objects.create(
            admin=self.request.user,
            action=f"Job status changed to {instance.status}",
            comment=instance.admin_comment or "",
            target=instance
        )


# -----------------------------
# ReviewLog Read-only ViewSet (optional)
# -----------------------------
class ReviewLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReviewLog.objects.all().order_by('-created_at')
    serializer_class = ReviewLogSerializer
    permission_classes = [permissions.IsAdminUser]

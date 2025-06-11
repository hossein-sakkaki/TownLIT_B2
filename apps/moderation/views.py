from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from utils.email.email_tools import send_custom_email
from .models import CollaborationRequest, JobApplication, AccessRequest, ReviewLog
from .utils import create_review_log
from .serializers import (
    CollaborationRequestSerializer,
    JobApplicationSerializer,
    ReviewLogSerializer,
    AccessRequestSerializer
)
from common.permissions import IsAdminOrReadOnly
import logging

logger = logging.getLogger(__name__)


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

    def create(self, request, *args, **kwargs):
        email = request.data.get("email")
        
        # Step 1 – Check for duplicate requests
        if AccessRequest.objects.filter(email=email).exists():
            logger.info(f"Duplicate access request attempt detected for email: {email}")
            return Response(
                {
                    "message": "You have already submitted a request with this email. "
                            "We will get back to you soon with an invitation after review."
                },
                status=status.HTTP_200_OK
            )

        # Step 2 – Proceed with saving the request
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_request = serializer.save()

        # Step 3 – Prepare email context
        subject = "🌟 You're Almost There — TownLIT Is Opening Its Doors"
        context = {
            "first_name": access_request.first_name,
            "email": access_request.email,
            "submitted_at": access_request.submitted_at,
            "site_domain": settings.SITE_URL,
            "logo_base_url": settings.EMAIL_LOGO_URL,
            "current_year": timezone.now().year,
        }

        # Step 4 – Send confirmation email
        success = send_custom_email(
            to=access_request.email,
            subject=subject,
            template_path="emails/forms/access_request_received.html",
            context=context,
        )

        if not success:
            logger.error(f"❌ Failed to send access request confirmation email to {access_request.email}")
            return Response(
                {
                    "error": "Your request was submitted, but we couldn’t send a confirmation email. "
                            "Please contact us if you don’t receive a response soon."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Step 5 – Return success response
        return Response(
            {
                "message": "Your access request has been received successfully. "
                        "A confirmation email has been sent to you."
            },
            status=status.HTTP_201_CREATED
        )

        

# ReviewLog Read-only ViewSet ----------------------------------------------------------
class ReviewLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReviewLog.objects.all().order_by('-created_at')
    serializer_class = ReviewLogSerializer
    permission_classes = [permissions.IsAdminUser]

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

import json
import os
from django.conf import settings
from django.http import FileResponse

from django.utils import timezone
from django.db.models import F
from datetime import timedelta

from .models import (
        TermsAndPolicy, FAQ, SiteAnnouncement, UserFeedback, UserActionLog, Prayer,
        VideoCategory, VideoSeries, OfficialVideo, VideoViewLog
    )
from .serializers import (
        TermsAndPolicySerializer, FAQSerializer, SiteAnnouncementSerializer,
        UserFeedbackSerializer, UserActionLogSerializer, PrayerSerializer,
        VideoCategorySerializer, VideoSeriesSerializer, OfficialVideoSerializer,
        OfficialVideoCreateUpdateSerializer, VideoViewLogSerializer
    )
from utils.common.ip import get_client_ip


from apps.config.choicemap import CHOICES_MAP
from utils.email.email_tools import send_custom_email
import logging

logger = logging.getLogger(__name__)

# TERMS AND POLICY ViewSet --------------------------------------------------------------------------------
class TermsAndPolicyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TermsAndPolicy.objects.all()
    serializer_class = TermsAndPolicySerializer
    permission_classes = [IsAdminUser]

    def get_permissions(self):
        
        if self.action in ['list', 'retrieve']:
            # Allow read-only access to all users
            permission_classes = [AllowAny]
        else:
            # Restrict write operations to admin users only
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]


# FAQ ViewSet ---------------------------------------------------------------------------------------------
class FAQViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    permission_classes = [IsAdminUser]

    def get_permissions(self):
        
        if self.action in ['list', 'retrieve']:
            # Allow read-only access to all users
            permission_classes = [AllowAny]
        else:
            # Restrict write operations to admin users only
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]


# SITE ANNOUNCEMENT ViewSet -------------------------------------------------------------------------------
class SiteAnnouncementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SiteAnnouncement.objects.all()
    serializer_class = SiteAnnouncementSerializer
    permission_classes = [IsAdminUser]

    def get_permissions(self):
        
        if self.action in ['list', 'retrieve']:
            # Allow read-only access to all users
            permission_classes = [AllowAny]
        else:
            # Restrict write operations to admin users only
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]


# USER FEEDBACK ViewSet -----------------------------------------------------------------------------------
class UserFeedbackViewSet(viewsets.ModelViewSet):
    serializer_class = UserFeedbackSerializer

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def get_permissions(self):
        if self.action in ['submit_feedback']:
            return [IsAuthenticated()]
        if self.action in ['list', 'retrieve', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return UserFeedback.objects.all()
        return UserFeedback.objects.filter(user=user)

    @action(detail=False, methods=['post'], url_path='submit-feedback', permission_classes=[IsAuthenticated])
    def submit_feedback(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        feedback = serializer.save(user=request.user)

        # Send confirmation email
        subject = "We've received your feedback – Thank you!"
        context = {
            'name': request.user.name or "Friend",
        }

        success = send_custom_email(
            to=request.user.email,
            subject=subject,
            template_path='emails/feedback/feedback_received_email.html',
            context=context,
            text_template_path=None
        )

        if success:
            logger.info(f"[UserFeedback] Confirmation email sent to {request.user.email} for feedback ID {feedback.id}")
            return Response(
                {"message": "Feedback submitted successfully. Confirmation email sent."},
                status=status.HTTP_201_CREATED
            )
        else:
            logger.warning(f"[UserFeedback] Feedback saved, but failed to send email to {request.user.email} for feedback ID {feedback.id}")
            return Response(
                {"message": "Feedback submitted successfully, but failed to send confirmation email."},
                status=status.HTTP_201_CREATED
            )
                

# USER ACTION LOG ViewSet ---------------------------------------------------------------------------------
class UserActionLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserActionLog.objects.all()
    serializer_class = UserActionLogSerializer
    permission_classes = [IsAdminUser]

    def get_permissions(self):
        
        if self.action in ['list', 'retrieve']:
            # Restrict read-only access to admin users
            permission_classes = [IsAdminUser]
        else:
            # Restrict write operations to admin users only
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]
    

# DESIGN TOKENS ViewSet ---------------------------------------------------------------------------------
class DesignTokensViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def get_tokens(self, request):
        try:
            file_path = os.path.join(settings.BASE_DIR, 'static', 'design-tokens.json')
            with open(file_path, 'r') as file:
                tokens = json.load(file)
            return Response(tokens, status=status.HTTP_200_OK)
        except FileNotFoundError:
            return Response({'error': 'Design tokens file not found'}, status=status.HTTP_404_NOT_FOUND)
        except json.JSONDecodeError:
            return Response({'error': 'Error parsing design tokens file'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ICONS ViewSet ---------------------------------------------------------------------------------
class IconViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def retrieve(self, request, pk=None):
        icon_name = pk
        icon_path = os.path.join(settings.BASE_DIR, 'static', 'icons', f"{icon_name}.svg")
        if not os.path.exists(icon_path):
            return Response({'error': 'Icon not found'}, status=404)        
        return FileResponse(open(icon_path, 'rb'), content_type='image/svg+xml')
    
    # Define the path to the icons directory
    def list(self, request):
        icons_path = os.path.join(settings.BASE_DIR, 'static', 'icons')
        if os.path.exists(icons_path):
            icons = [f.split('.')[0] for f in os.listdir(icons_path) if f.endswith('.svg')]
        else:
            icons = []
        return Response({'icons': icons})
    
    
# STATIC CHOICE MAP ViewSet -------------------------------------------------------------------------
class StaticChoiceViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['get'], url_path='(?P<choice_name>[a-zA-Z_-]+)')
    def get_static_choice(self, request, choice_name):
        choices = CHOICES_MAP.get(choice_name)
        if choices is None:
            return Response({"error": f"Choice '{choice_name}' not found."}, status=404)
        return Response(choices)


class PrayerPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
# PRAYER View -----------------------------------------------------------------------------------------------
class PrayerViewSet(viewsets.ModelViewSet):
    queryset = Prayer.objects.all().order_by('-submitted_at')
    serializer_class = PrayerSerializer
    pagination_class = PrayerPagination

    def get_permissions(self):
        if self.action == 'respond':
            return [IsAdminUser()]
        elif self.action in ['list']:
            return [AllowAny()]
        return [AllowAny()]  # create allowed for everyone

    def get_queryset(self):
        if self.action == 'list':
            return Prayer.objects.filter(is_active=True, allow_display=True).order_by('-submitted_at')
        return super().get_queryset()
    
    @method_decorator(ratelimit(key='user_or_ip', rate='5/m', method='POST', block=True))
    def create(self, request, *args, **kwargs):
        # Honeypot field check
        if request.data.get("company_name", "").strip():
            raise ValidationError({"non_field_errors": ["Spam detected."]})

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        return Response(
            {
                "message": "Your response has been saved and added beneath the prayer. Thank you for ministering in grace.",
                "prayer": serializer.data
            },
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def respond(self, request, pk=None):
        prayer = self.get_object()
        response_text = request.data.get("admin_response")
        if not response_text:
            return Response(
                {"error": "Please provide a message to include in your response."},
                status=status.HTTP_400_BAD_REQUEST
            )
        prayer.admin_response = response_text
        prayer.responded_by = request.user
        prayer.responded_at = timezone.now()
        prayer.save()
        return Response(
            {
                "message": "Your response has been saved and added beneath the prayer. Thank you for ministering in grace.",
                "prayer_id": prayer.id
            },
            status=status.HTTP_200_OK
        )
    
    
    @action(detail=False, methods=["get"], url_path="total-count")
    def total_count(self, request):
        total = Prayer.objects.filter(is_active=True).count()
        return Response({"total": total})


# VIDEO CATEGORY View -----------------------------------------------------------------------------------------
class VideoCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VideoCategory.objects.filter(is_active=True)
    serializer_class = VideoCategorySerializer
    permission_classes = [AllowAny]
    
    
class VideoSeriesViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VideoSeries.objects.filter(is_active=True)
    serializer_class = VideoSeriesSerializer
    permission_classes = [AllowAny]
    

class OfficialVideoViewSet(viewsets.ModelViewSet):
    queryset = OfficialVideo.objects.filter(is_active=True, publish_date__lte=timezone.now())
    serializer_class = OfficialVideoSerializer
    permission_classes = [AllowAny]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['language', 'category', 'series', 'parent']
    search_fields = ['title', 'description']
    ordering_fields = ['publish_date', 'view_count', 'episode_number', 'created_at']
    ordering = ['-publish_date']


    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return OfficialVideoCreateUpdateSerializer
        return OfficialVideoSerializer

    @action(detail=True, methods=["post"], permission_classes=[AllowAny])
    def track_view(self, request, pk=None):
        video = self.get_object()
        ip = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]

        # فقط اگر در 6 ساعت گذشته همین IP این ویدیو را ندیده باشد
        recent_time = timezone.now() - timedelta(hours=6)
        if not VideoViewLog.objects.filter(video=video, ip_address=ip, viewed_at__gte=recent_time).exists():
            video.view_count = F("view_count") + 1
            video.save(update_fields=["view_count"])
            VideoViewLog.objects.create(
                video=video,
                ip_address=ip,
                user_agent=user_agent
            )

        return Response({"message": "View registered"}, status=status.HTTP_200_OK)
    

class VideoViewLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VideoViewLog.objects.all()
    serializer_class = VideoViewLogSerializer
    permission_classes = [IsAdminUser]

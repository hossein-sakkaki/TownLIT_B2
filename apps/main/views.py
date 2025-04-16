from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.decorators import action
import json
import os
from django.conf import settings
from django.http import FileResponse

from .models import TermsAndPolicy, FAQ, SiteAnnouncement, UserFeedback, UserActionLog
from .serializers import TermsAndPolicySerializer, FAQSerializer, SiteAnnouncementSerializer, UserFeedbackSerializer, UserActionLogSerializer
from apps.config.choicemap import CHOICES_MAP




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
    queryset = UserFeedback.objects.all()
    serializer_class = UserFeedbackSerializer
    permission_classes = [IsAdminUser]

    def get_permissions(self):
        
        if self.action in ['list', 'retrieve', 'create']:
            # Allow read-only access and create for all users
            permission_classes = [AllowAny]
        else:
            # Restrict update and delete operations to admin users only
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]


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

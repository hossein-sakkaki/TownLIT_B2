from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    EmailCampaignPreviewView, ExternalCampaignPreviewView, EmailTemplatePreviewView, 
    UnsubscribeHTMLView, ResubscribeView, ExternalUnsubscribeView,
    preview_reset_password
)

router = DefaultRouter()

app_name = 'communication'
urlpatterns = [
    path('campaigns/<int:pk>/preview/', EmailCampaignPreviewView.as_view(), name='email-campaign-preview'),
    path('external-campaigns/<int:pk>/preview/', ExternalCampaignPreviewView.as_view(), name='external-campaign-preview'),
    path('templates/<int:pk>/preview/', EmailTemplatePreviewView.as_view(), name='email-template-preview'),

    path('unsubscribe/<str:token>/', UnsubscribeHTMLView.as_view(), name='unsubscribe'),
    path('resubscribe/<str:token>/', ResubscribeView.as_view(), name='resubscribe'),
    path('external-unsubscribe/<str:token>/', ExternalUnsubscribeView.as_view(), name='external-unsubscribe'),
    
    path("email-preview/email-test/", preview_reset_password, name="email_preview_reset"),
]

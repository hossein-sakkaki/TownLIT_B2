from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import EmailCampaignPreviewView, EmailTemplatePreviewView, UnsubscribeHTMLView

router = DefaultRouter()

app_name = 'communication'
urlpatterns = [
    path('campaigns/<int:pk>/preview/', EmailCampaignPreviewView.as_view(), name='email-campaign-preview'),
    path('templates/<int:pk>/preview/', EmailTemplatePreviewView.as_view(), name='email-template-preview'),
    path('unsubscribe/<str:token>/', UnsubscribeHTMLView.as_view(), name='unsubscribe'),


]

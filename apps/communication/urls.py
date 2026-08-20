# apps/communication/urls.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-20.


from django.urls import path

from .views import (
    EmailCampaignPreviewView,
    EmailClickTrackingView,
    EmailOpenTrackingView,
    EmailTemplatePreviewView,
    ExternalCampaignPreviewView,
    ExternalUnsubscribeView,
    ResubscribeView,
    UnsubscribeHTMLView,
    preview_reset_password,
)


app_name = "communication"


urlpatterns = [
    # Admin previews.
    path(
        "campaigns/<int:pk>/preview/",
        EmailCampaignPreviewView.as_view(),
        name="email-campaign-preview",
    ),
    path(
        "templates/<int:pk>/preview/",
        EmailTemplatePreviewView.as_view(),
        name="email-template-preview",
    ),

    # Legacy external campaign preview.
    path(
        "external-campaigns/<int:pk>/preview/",
        ExternalCampaignPreviewView.as_view(),
        name="external-campaign-preview",
    ),

    # Subscription preferences.
    path(
        "unsubscribe/<str:token>/",
        UnsubscribeHTMLView.as_view(),
        name="email-unsubscribe",
    ),
    path(
        "resubscribe/<str:token>/",
        ResubscribeView.as_view(),
        name="email-resubscribe",
    ),

    # Legacy external unsubscribe compatibility.
    path(
        "external-unsubscribe/<str:token>/",
        ExternalUnsubscribeView.as_view(),
        name="external-email-unsubscribe",
    ),

    # Email engagement tracking.
    path(
        "track/open/<str:token>.gif",
        EmailOpenTrackingView.as_view(),
        name="email-track-open",
    ),
    path(
        "track/click/<str:token>/",
        EmailClickTrackingView.as_view(),
        name="email-track-click",
    ),

    # Legacy internal preview.
    path(
        "email-preview/email-test/",
        preview_reset_password,
        name="email-test-preview",
    ),
]
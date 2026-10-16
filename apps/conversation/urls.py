# apps/conversation/urls.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DialogueViewSet, MessageViewSet, UserDialogueMarkerViewSet
from .views.organization import (
    CLOSE_VIEW,
    REOPEN_VIEW,
    RESOLVE_VIEW,
    OrganizationDirectInboxUnreadCountView,
    OrganizationDirectInboxView,
    OrganizationDirectOperatorAssignView,
    OrganizationDirectOperatorConversationView,
    OrganizationDirectOperatorReadView,
    OrganizationDirectOperatorReplyView,
    OrganizationDirectParticipantConversationView,
    OrganizationDirectParticipantMessageView,
    OrganizationDirectParticipantReadView,
)


router = DefaultRouter()
router.register(r"dialogues", DialogueViewSet, basename="dialogue")
router.register(r"messages", MessageViewSet, basename="message")
router.register(r"markers", UserDialogueMarkerViewSet, basename="marker")


app_name = "conversation"
urlpatterns = [
    path(
        "organizations/<slug:organization_slug>/messenger/conversation/",
        OrganizationDirectParticipantConversationView.as_view(),
        name="organization-direct-participant-conversation",
    ),
    path(
        "organizations/<slug:organization_slug>/messenger/conversation/messages/",
        OrganizationDirectParticipantMessageView.as_view(),
        name="organization-direct-participant-message",
    ),
    path(
        "organizations/<slug:organization_slug>/messenger/conversation/read/",
        OrganizationDirectParticipantReadView.as_view(),
        name="organization-direct-participant-read",
    ),
    path(
        "organizations/<slug:organization_slug>/messenger/inbox/",
        OrganizationDirectInboxView.as_view(),
        name="organization-direct-inbox",
    ),
    path(
        "organizations/<slug:organization_slug>/messenger/inbox/unread-count/",
        OrganizationDirectInboxUnreadCountView.as_view(),
        name="organization-direct-inbox-unread-count",
    ),
    path(
        "organizations/<slug:organization_slug>/messenger/conversations/<slug:dialogue_slug>/",
        OrganizationDirectOperatorConversationView.as_view(),
        name="organization-direct-operator-conversation",
    ),
    path(
        "organizations/<slug:organization_slug>/messenger/conversations/<slug:dialogue_slug>/reply/",
        OrganizationDirectOperatorReplyView.as_view(),
        name="organization-direct-operator-reply",
    ),
    path(
        "organizations/<slug:organization_slug>/messenger/conversations/<slug:dialogue_slug>/read/",
        OrganizationDirectOperatorReadView.as_view(),
        name="organization-direct-operator-read",
    ),
    path(
        "organizations/<slug:organization_slug>/messenger/conversations/<slug:dialogue_slug>/assign/",
        OrganizationDirectOperatorAssignView.as_view(),
        name="organization-direct-operator-assign",
    ),
    path(
        "organizations/<slug:organization_slug>/messenger/conversations/<slug:dialogue_slug>/resolve/",
        RESOLVE_VIEW,
        name="organization-direct-operator-resolve",
    ),
    path(
        "organizations/<slug:organization_slug>/messenger/conversations/<slug:dialogue_slug>/reopen/",
        REOPEN_VIEW,
        name="organization-direct-operator-reopen",
    ),
    path(
        "organizations/<slug:organization_slug>/messenger/conversations/<slug:dialogue_slug>/close/",
        CLOSE_VIEW,
        name="organization-direct-operator-close",
    ),
    path("", include(router.urls)),
]

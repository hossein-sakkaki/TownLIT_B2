# apps/profiles/urls.py

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.profiles.views.member import MemberViewSet
from apps.profiles.views.guest import GuestUserViewSet
from apps.profiles.views.profile_me_view import ProfileMeView
from apps.profiles.views.profile_migration import ProfileMigrationViewSet
from apps.profiles.views.member_services import MemberServicesViewSet
from apps.profiles.views.visitor_profile import VisitorProfileViewSet
from apps.profiles.views.friendship import FriendshipViewSet
from apps.profiles.views.fellowship import FellowshipViewSet
from apps.profiles.views.spiritual_gifts import (
    MemberSpiritualGiftsViewSet,
    SpiritualGiftSurveyQuestionViewSet,
    SpiritualGiftSurveyViewSet,
)

router = DefaultRouter()
router.register(r"members", MemberViewSet, basename="member")
router.register(r"guestusers", GuestUserViewSet, basename="guestuser")
router.register(r"migrate", ProfileMigrationViewSet, basename="profile-migration")
router.register(r"friendships", FriendshipViewSet, basename="friendship")
router.register(r"fellowship", FellowshipViewSet, basename="fellowship")
router.register(r"spiritual-gift", MemberSpiritualGiftsViewSet, basename="spiritual-gift")
router.register(r"spiritual-gift-survey-questions", SpiritualGiftSurveyQuestionViewSet, basename="spiritual-gift-survey-questions")
router.register(r"spiritual-gift-survey", SpiritualGiftSurveyViewSet, basename="spiritual-gift-survey")

services_catalog = MemberServicesViewSet.as_view({"get": "services_catalog"})
my_services = MemberServicesViewSet.as_view({"get": "my_services"})
create_service = MemberServicesViewSet.as_view({"post": "create_service"})
detail_service = MemberServicesViewSet.as_view({"patch": "update_service", "delete": "delete_service"})
services_policy = MemberServicesViewSet.as_view({"get": "policy"})

custom_paths = [
    path("me/", ProfileMeView.as_view(), name="profile-me"),

    # Unified public profile
    path(
        "profile/<str:username>/",
        VisitorProfileViewSet.as_view({"get": "unified_profile"}),
        name="unified-profile-detail",
    ),
    path(
        "profile/<str:username>/moments/",
        VisitorProfileViewSet.as_view({"get": "unified_moments"}),
        name="unified-profile-moments",
    ),

    # Member public profile
    path(
        "members/profile/<str:username>/",
        VisitorProfileViewSet.as_view({"get": "profile"}),
        name="profile-detail",
    ),
    path(
        "members/profile/<str:username>/moments/",
        VisitorProfileViewSet.as_view({"get": "moments"}),
        name="profile-moments",
    ),
    path(
        "members/profile/<str:username>/prayers/",
        VisitorProfileViewSet.as_view({"get": "prayers"}),
        name="profile-prayers",
    ),

    # Guest public profile
    path(
        "guestusers/profile/<str:username>/",
        GuestUserViewSet.as_view({"get": "profile"}),
        name="guestuser-profile-detail",
    ),
    path(
        "guestusers/profile/<str:username>/moments/",
        GuestUserViewSet.as_view({"get": "moments"}),
        name="guestuser-profile-moments",
    ),

    # Backward-compatible guest detail
    path(
        "guestusers/<int:pk>/",
        GuestUserViewSet.as_view({"get": "view_guest_profile"}),
        name="guestuser-detail",
    ),

    # Member services
    path("members/services-catalog/", services_catalog, name="member-services-catalog"),
    path("members/my-services/", my_services, name="member-my-services"),
    path("members/services/", create_service, name="member-services-create"),
    path("members/services/<int:pk>/", detail_service, name="member-services-detail"),
    path("members/services-policy/", services_policy, name="member-services-policy"),
]

urlpatterns = custom_paths + router.urls
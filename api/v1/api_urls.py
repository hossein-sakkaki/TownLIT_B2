# townlit_b/api_urls.py

from rest_framework_nested.routers import NestedSimpleRouter
from rest_framework.routers import DefaultRouter
from django.urls import path, include

# === parent viewsets ===
from apps.profiles.views import MemberViewSet, GuestUserViewSet
from apps.profilesOrg.views import OrganizationViewSet, ChurchViewSet, MissionOrganizationViewSet, ChristianPublishingHouseViewSet, ChristianWorshipMinistryViewSet, ChristianCounselingCenterViewSet, ChristianConferenceCenterViewSet, ChristianEducationalInstitutionViewSet
from apps.posts.views import (
    MomentViewSet, TestimonyViewSet, PrayViewSet, AnnouncementViewSet,
    WitnessViewSet, PreachViewSet, LessonViewSet, WorshipViewSet,
    ServiceEventViewSet, MissionViewSet, LibraryViewSet, ConferenceViewSet,
    FutureConferenceViewSet, MediaContentViewSet
)
from apps.accounts.views import SocialLinksViewSet
from apps.sanctuary.views import SanctuaryReviewViewSet

# === root router ===
router = DefaultRouter()
router.register(r'members', MemberViewSet, basename='member')
router.register(r'guestusers', GuestUserViewSet, basename='guestuser')
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'churches', ChurchViewSet, basename='church')
router.register(r'mission-organizations', MissionOrganizationViewSet, basename='mission-organization')
router.register(r'publishing-houses', ChristianPublishingHouseViewSet, basename='publishing-house')
router.register(r'worship-ministries', ChristianWorshipMinistryViewSet, basename='worship-ministry')
router.register(r'counseling-centers', ChristianCounselingCenterViewSet, basename='counseling-center')
router.register(r'conference-centers', ChristianConferenceCenterViewSet, basename='conference-center')
router.register(r'educational-institutions', ChristianEducationalInstitutionViewSet, basename='educational-institution')

# === nested: social links ===
members_router = NestedSimpleRouter(router, r'members', lookup='member')
members_router.register(r'social-links', SocialLinksViewSet, basename='member-social-links')
members_router.register(r'moments', MomentViewSet, basename='member-moments')
members_router.register(r'testimonies', TestimonyViewSet, basename='member-testimonies')
members_router.register(r'prayers', PrayViewSet, basename='member-prayers')

guestusers_router = NestedSimpleRouter(router, r'guestusers', lookup='guestuser')
guestusers_router.register(r'social-links', SocialLinksViewSet, basename='guestuser-social-links')
guestusers_router.register(r'moments', MomentViewSet, basename='guestuser-moments')

organizations_router = NestedSimpleRouter(router, r'organizations', lookup='organization')
organizations_router.register(r'social-links', SocialLinksViewSet, basename='organization-social-links')
organizations_router.register(r'moments', MomentViewSet, basename='organization-moments')
organizations_router.register(r'announcements', AnnouncementViewSet, basename='organization-announcements')
organizations_router.register(r'witnesses', WitnessViewSet, basename='organization-witnesses')

# === nested: churches ===
church_router = NestedSimpleRouter(router, r'churches', lookup='church')
church_router.register(r'preaches', PreachViewSet, basename='church-preaches')
church_router.register(r'lessons', LessonViewSet, basename='church-lessons')
church_router.register(r'worships', WorshipViewSet, basename='church-worships')

# === nested: mission-org ===
mission_router = NestedSimpleRouter(router, r'mission-organizations', lookup='mission_organization')
mission_router.register(r'missions', MissionViewSet, basename='mission-organization-missions')
mission_router.register(r'testimonies', TestimonyViewSet, basename='mission-testimonies')

# === nested: publishing houses ===
publishing_router = NestedSimpleRouter(router, r'publishing-houses', lookup='publishing_house')
publishing_router.register(r'libraries', LibraryViewSet, basename='publishing-house-libraries')

# === nested: worship ministries ===
worship_router = NestedSimpleRouter(router, r'worship-ministries', lookup='worship_ministry')
worship_router.register(r'worships', WorshipViewSet, basename='worship-ministry-worships')
worship_router.register(r'worship-schedule', ServiceEventViewSet, basename='worship-ministry-worship-schedule')
worship_router.register(r'worship-testimonies', TestimonyViewSet, basename='worship-ministry-worship-testimonies')

# === nested: counseling centers ===
counseling_router = NestedSimpleRouter(router, r'counseling-centers', lookup='counseling_center')
counseling_router.register(r'services', ServiceEventViewSet, basename='counseling-center-services')
counseling_router.register(r'testimonials', TestimonyViewSet, basename='counseling-center-testimonials')

# === nested: conference centers ===
conference_router = NestedSimpleRouter(router, r'conference-centers', lookup='conference_center')
conference_router.register(r'service-events', ServiceEventViewSet, basename='conference-center-events')
conference_router.register(r'conferences', ConferenceViewSet, basename='conference-center-conferences')
conference_router.register(r'future-conferences', FutureConferenceViewSet, basename='conference-center-future')
conference_router.register(r'testimonials', TestimonyViewSet, basename='conference-center-testimonials')

# === nested: educational institutions ===
education_router = NestedSimpleRouter(router, r'educational-institutions', lookup='educational_institution')
education_router.register(r'testimonies', TestimonyViewSet, basename='institution-testimonies')

# === nested: sanctuary-requests/<id>/reviews/
from apps.sanctuary.views import SanctuaryRequestViewSet
router.register(r'sanctuary-requests', SanctuaryRequestViewSet, basename='sanctuary-request')

sanctuary_router = NestedSimpleRouter(router, r'sanctuary-requests', lookup='sanctuary_request')
sanctuary_router.register(r'reviews', SanctuaryReviewViewSet, basename='sanctuary-request-reviews')

# === نهایی
urlpatterns = (
    router.urls +
    members_router.urls +
    guestusers_router.urls +
    organizations_router.urls +
    church_router.urls +
    mission_router.urls +
    publishing_router.urls +
    worship_router.urls +
    counseling_router.urls +
    conference_router.urls +
    education_router.urls +
    sanctuary_router.urls
)

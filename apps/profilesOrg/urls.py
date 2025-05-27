from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    OrganizationViewSet,
    OrganizationManagerViewSet,
    ChurchViewSet,
    MissionOrganizationViewSet,
    ChristianPublishingHouseViewSet,
    ChristianWorshipMinistryViewSet,
    ChristianCounselingCenterViewSet,
    ChristianConferenceCenterViewSet,
    ChristianEducationalInstitutionViewSet,
    ChristianChildrenOrganizationViewSet,
    ChristianYouthOrganizationViewSet,
    ChristianWomensOrganizationViewSet,
    ChristianMensOrganizationViewSet,
)

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'organization-managers', OrganizationManagerViewSet, basename='organization-manager')
router.register(r'churches', ChurchViewSet, basename='church')
router.register(r'mission-organizations', MissionOrganizationViewSet, basename='mission-organization')
router.register(r'publishing-houses', ChristianPublishingHouseViewSet, basename='publishing-house')
router.register(r'worship-ministries', ChristianWorshipMinistryViewSet, basename='worship-ministry')
router.register(r'counseling-centers', ChristianCounselingCenterViewSet, basename='counseling-center')
router.register(r'conference-centers', ChristianConferenceCenterViewSet, basename='conference-center')
router.register(r'educational-institutions', ChristianEducationalInstitutionViewSet, basename='educational-institution')
router.register(r'children-organizations', ChristianChildrenOrganizationViewSet, basename='children-organization')
router.register(r'youth-organizations', ChristianYouthOrganizationViewSet, basename='youth-organization')
router.register(r'womens-organizations', ChristianWomensOrganizationViewSet, basename='womens-organization')
router.register(r'mens-organizations', ChristianMensOrganizationViewSet, basename='mens-organization')

urlpatterns = router.urls

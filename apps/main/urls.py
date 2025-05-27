from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    TermsAndPolicyViewSet,
    FAQViewSet,
    SiteAnnouncementViewSet,
    UserFeedbackViewSet,
    UserActionLogViewSet,
    DesignTokensViewSet,
    IconViewSet,
    StaticChoiceViewSet,
    VideoCategoryViewSet,
    VideoSeriesViewSet,
    OfficialVideoViewSet,
    PrayerViewSet,
)

router = DefaultRouter()
router.register(r'terms-and-policies', TermsAndPolicyViewSet, basename='terms-and-policies')
router.register(r'faqs', FAQViewSet, basename='faqs')
router.register(r'site-announcements', SiteAnnouncementViewSet, basename='site-announcements')
router.register(r'user-feedbacks', UserFeedbackViewSet, basename='user-feedback')
router.register(r'user-action-logs', UserActionLogViewSet, basename='user-action-logs')
router.register(r'design-tokens', DesignTokensViewSet, basename='design-tokens')
router.register(r'icons', IconViewSet, basename='icons')
router.register(r'static-choice', StaticChoiceViewSet, basename='static-choice')
router.register(r'video-categories', VideoCategoryViewSet, basename='video-categories')
router.register(r'video-series', VideoSeriesViewSet, basename='video-series')
router.register(r'official-videos', OfficialVideoViewSet, basename='official-videos')
router.register(r'prayers', PrayerViewSet, basename='prayers')

urlpatterns = router.urls







# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from rest_framework_nested import routers

# # from apps.accounts.views import AuthViewSet, SocialLinksViewSet
# from .views import (
#                 TermsAndPolicyViewSet,
#                 FAQViewSet,
#                 SiteAnnouncementViewSet,
#                 UserFeedbackViewSet,
#                 UserActionLogViewSet,
#                 DesignTokensViewSet,
#                 IconViewSet,
#                 StaticChoiceViewSet,
#                 VideoCategoryViewSet, 
#                 VideoSeriesViewSet, 
#                 OfficialVideoViewSet,
#                 PrayerViewSet
#             )
# # from apps.profiles.views import (
# #                 MemberViewSet, GuestUserViewSet, ProfileMigrationViewSet, 
# #                 FriendshipViewSet, FellowshipViewSet, VeriffViewSet,
# #                 SpiritualGiftSurveyViewSet, SpiritualGiftSurveyQuestionViewSet, MemberSpiritualGiftsViewSet
# #             )
# # from apps.notifications.views import MainNotificationViewSet
# # from apps.posts.views import (
# #                 MomentViewSet, TestimonyViewSet, PrayViewSet, AnnouncementViewSet, 
# #                 WitnessViewSet, PreachViewSet, LessonViewSet, WorshipViewSet, 
# #                 MediaContentViewSet, MissionViewSet, LibraryViewSet, ServiceEventViewSet, 
# #                 ConferenceViewSet, FutureConferenceViewSet
# #             )
# # from apps.profilesOrg.views import (
# #                 OrganizationViewSet, OrganizationManagerViewSet, ChurchViewSet, 
# #                 MissionOrganizationViewSet, ChristianPublishingHouseViewSet, 
# #                 ChristianWorshipMinistryViewSet, ChristianCounselingCenterViewSet, 
# #                 CounselingServiceViewSet, ChristianConferenceCenterViewSet, 
# #                 ChristianEducationalInstitutionViewSet, ChristianChildrenOrganizationViewSet, 
# #                 ChristianYouthOrganizationViewSet, ChristianWomensOrganizationViewSet, 
# #                 ChristianMensOrganizationViewSet
# #             )
# # from apps.sanctuary.views import (
# #                 SanctuaryRequestViewSet, SanctuaryReviewViewSet, SanctuaryOutcomeViewSet,
# #                 AdminSanctuaryReviewViewSet, SanctuaryHistoryViewSet
# #             )

# # Main Router
# router = DefaultRouter()
# # router.register(r'auth', AuthViewSet, basename='auth')
# # router.register(r'members', MemberViewSet, basename='member')
# # router.register(r'guestusers', GuestUserViewSet, basename='guestuser')
# # router.register(r'migrate', ProfileMigrationViewSet, basename='profile-migration')
# # router.register(r'friendships', FriendshipViewSet, basename='friendships')
# # router.register(r'fellowship', FellowshipViewSet, basename='fellowship')





# # Social Media Links -------------------------------------------------------------------------
# # router.register(r'members', SocialLinksViewSet, basename='members')
# # router.register(r'organizations', SocialLinksViewSet, basename='organizations')
# # router.register(r'guestusers', SocialLinksViewSet, basename='guestusers')
# # router.register(r'social-links', SocialLinksViewSet, basename='social-links')

# # # Nested routers for social-links
# # members_router = routers.NestedSimpleRouter(router, r'members', lookup='member')
# # members_router.register(r'social-links', SocialLinksViewSet, basename='member-social-links')

# # organizations_router = routers.NestedSimpleRouter(router, r'organizations', lookup='organization')
# # organizations_router.register(r'social-links', SocialLinksViewSet, basename='organization-social-links')

# # guestusers_router = routers.NestedSimpleRouter(router, r'guestusers', lookup='guestuser')
# # guestusers_router.register(r'social-links', SocialLinksViewSet, basename='guestuser-social-links')




# # # Notifications -------------------------------------------------------------------------------
# # router.register(r'notifications', MainNotificationViewSet, basename='notifications')

# # # Gift Survey ---------------------------------------------------------------------------------
# # router.register(r'spiritual-gift', MemberSpiritualGiftsViewSet, basename='spiritual-gift')
# # router.register(r'spiritual-gift-survey-questions', SpiritualGiftSurveyQuestionViewSet, basename='spiritual-gift-survey-questions')
# # router.register(r'spiritual-gift-survey', SpiritualGiftSurveyViewSet, basename='spiritual-gift-survey')

# # Just Main App Router -------------------------------------------------------------------------
# router.register(r'design-tokens', DesignTokensViewSet, basename='design-tokens')
# router.register(r'icons', IconViewSet, basename='icon')
# router.register(r'static-choice', StaticChoiceViewSet, basename='static-choice')
# router.register(r'terms-and-policies', TermsAndPolicyViewSet, basename='terms-and-policies')
# router.register(r'faqs', FAQViewSet, basename='faqs')
# router.register(r'site-announcements', SiteAnnouncementViewSet, basename='site-announcements')
# router.register(r'user-feedbacks', UserFeedbackViewSet, basename='user-feedback')
# router.register(r'user-action-logs', UserActionLogViewSet, basename='user-action-logs')
# router.register(r'prayers', PrayerViewSet, basename='prayer')

# # Official Section Routers -------------------------------------------------------------------
# router.register(r'video-categories', VideoCategoryViewSet, basename='video-category')
# router.register(r'video-series', VideoSeriesViewSet, basename='video-series')
# router.register(r'official-videos', OfficialVideoViewSet, basename='official-video')   


# # # Sanctuary Router for requests, outcomes, reviews
# # router.register(r'sanctuary-requests', SanctuaryRequestViewSet, basename='sanctuary-request')
# # router.register(r'sanctuary-outcomes', SanctuaryOutcomeViewSet, basename='sanctuary-outcome')
# # router.register(r'sanctuary-reviews', SanctuaryReviewViewSet, basename='sanctuary-review')
# # router.register(r'admin-sanctuary-reviews', AdminSanctuaryReviewViewSet, basename='admin-sanctuary-review')

# # Organization-based Router
# # router.register(r'organizations', OrganizationViewSet, basename='organization')
# # router.register(r'churches', ChurchViewSet, basename='church')
# # router.register(r'mission-organizations', MissionOrganizationViewSet, basename='mission-organization')
# # router.register(r'publishing-houses', ChristianPublishingHouseViewSet, basename='publishing-house')
# # router.register(r'worship-ministries', ChristianWorshipMinistryViewSet, basename='worship-ministry')
# # router.register(r'counseling-centers', ChristianCounselingCenterViewSet, basename='counseling-center')
# # router.register(r'conference-centers', ChristianConferenceCenterViewSet, basename='conference-center')
# # router.register(r'educational-institutions', ChristianEducationalInstitutionViewSet, basename='educational-institution')
# # router.register(r'children-organizations', ChristianChildrenOrganizationViewSet, basename='children-organization')
# # router.register(r'youth-organizations', ChristianYouthOrganizationViewSet, basename='youth-organization')
# # router.register(r'womens-organizations', ChristianWomensOrganizationViewSet, basename='womens-organization')
# # router.register(r'mens-organizations', ChristianMensOrganizationViewSet, basename='mens-organization')
# # router.register(r'organization-managers', OrganizationManagerViewSet, basename='organization-manager')

# # Nested Routers for Sanctuary Reviews related to requests
# sanctuary_request_nested_router = routers.NestedSimpleRouter(router, r'sanctuary-requests', lookup='sanctuary_request')
# sanctuary_request_nested_router.register(r'reviews', SanctuaryReviewViewSet, basename='sanctuary-request-reviews')

# # Nested Routers for members and guestusers
# member_router = routers.NestedSimpleRouter(router, r'members', lookup='member')
# # member_router.register(r'moments', MomentViewSet, basename='member-moments')
# # member_router.register(r'testimonies', TestimonyViewSet, basename='member-testimonies')
# # member_router.register(r'prayers', PrayViewSet, basename='member-prayers')

# # guestuser_router = routers.NestedSimpleRouter(router, r'guestusers', lookup='guestuser')
# # guestuser_router.register(r'moments', MomentViewSet, basename='guestuser-moments')

# # # Nested Routers for Organization Services and Moments
# # organization_router = routers.NestedSimpleRouter(router, r'organizations', lookup='organization')
# # organization_router.register(r'moments', MomentViewSet, basename='organization-moments')
# # organization_router.register(r'announcements', AnnouncementViewSet, basename='organization-announcements')
# # organization_router.register(r'witnesses', WitnessViewSet, basename='organization-witnesses')

# # # Church Nested Routers for Services
# # church_router = routers.NestedSimpleRouter(router, r'churches', lookup='church')
# # church_router.register(r'preaches', PreachViewSet, basename='church-preaches')
# # church_router.register(r'lessons', LessonViewSet, basename='church-lessons')
# # church_router.register(r'worships', WorshipViewSet, basename='church-worships')

# # # Mission Organization Nested Routers
# # mission_router = routers.NestedSimpleRouter(router, r'mission-organizations', lookup='mission_organization')
# # mission_router.register(r'missions', MissionViewSet, basename='mission-organization-missions')
# # mission_router.register(r'testimonies', TestimonyViewSet, basename='mission-testimonies')

# # # Publishing House Nested Routers
# # publishing_house_router = routers.NestedSimpleRouter(router, r'publishing-houses', lookup='publishing_house')
# # publishing_house_router.register(r'libraries', LibraryViewSet, basename='publishing-house-libraries')

# # # Worship Ministry Nested Routers
# # worship_ministry_router = routers.NestedSimpleRouter(router, r'worship-ministries', lookup='worship_ministry')
# # worship_ministry_router.register(r'worship-schedule', ServiceEventViewSet, basename='worship-ministry-worship-schedule')
# # worship_ministry_router.register(r'worships', WorshipViewSet, basename='worship-ministry-worships')
# # worship_ministry_router.register(r'worship-testimonies', TestimonyViewSet, basename='worship-ministry-worship-testimonies')

# # # Counseling Center Nested Routers
# # counseling_center_router = routers.NestedSimpleRouter(router, r'counseling-centers', lookup='counseling_center')
# # counseling_center_router.register(r'testimonials', TestimonyViewSet, basename='counseling-center-testimonials')
# # # counseling_center_router.register(r'services', CounselingServiceViewSet, basename='counseling-center-services')

# # # Conference Center Nested Routers
# # conference_center_router = routers.NestedSimpleRouter(router, r'conference-centers', lookup='conference_center')
# # conference_center_router.register(r'service-events', ServiceEventViewSet, basename='conference-center-schedule')
# # conference_center_router.register(r'conferences', ConferenceViewSet, basename='conference-center-conferences')
# # conference_center_router.register(r'future-conferences', FutureConferenceViewSet, basename='conference-center-future-conferences')
# # conference_center_router.register(r'testimonials', TestimonyViewSet, basename='conference-center-testimonials')

# # # Educational Institution Nested Routers
# # institution_router = routers.NestedSimpleRouter(router, r'educational-institutions', lookup='educational_institution')
# # institution_router.register(r'testimonies', TestimonyViewSet, basename='institution-testimonies')

# # # Children Organization Nested Routers
# # children_org_router = routers.NestedSimpleRouter(router, r'children-organizations', lookup='children_organization')
# # children_org_router.register(r'worships', WorshipViewSet, basename='children-organization-worships')
# # children_org_router.register(r'educations', LessonViewSet, basename='children-organization-educations')
# # children_org_router.register(r'child-events', ServiceEventViewSet, basename='children-organization-child-events')
# # children_org_router.register(r'child-testimonies', TestimonyViewSet, basename='children-organization-child-testimonies')

# # # Youth Organization Nested Routers
# # youth_org_router = routers.NestedSimpleRouter(router, r'youth-organizations', lookup='youth_organization')
# # youth_org_router.register(r'youth-events', ServiceEventViewSet, basename='youth-organization-events')
# # youth_org_router.register(r'youth-worships', WorshipViewSet, basename='youth-organization-worships')
# # youth_org_router.register(r'youth-educations', LessonViewSet, basename='youth-organization-educations')
# # youth_org_router.register(r'youth-media', MediaContentViewSet, basename='youth-organization-media')
# # youth_org_router.register(r'youth-testimonies', TestimonyViewSet, basename='youth-organization-testimonies')

# # # Women Organization Nested Routers
# # womens_org_router = routers.NestedSimpleRouter(router, r'womens-organizations', lookup='womens_organization')
# # womens_org_router.register(r'women-events', ServiceEventViewSet, basename='womens-organization-events')
# # womens_org_router.register(r'women-educations', LessonViewSet, basename='womens-organization-educations')
# # womens_org_router.register(r'women-testimonies', TestimonyViewSet, basename='womens-organization-testimonies')

# # # Men Organization Nested Routers
# # mens_org_router = routers.NestedSimpleRouter(router, r'mens-organizations', lookup='mens_organization')
# # mens_org_router.register(r'men-events', ServiceEventViewSet, basename='mens-organization-events')
# # mens_org_router.register(r'men-educations', LessonViewSet, basename='mens-organization-educations')
# # mens_org_router.register(r'men-testimonies', TestimonyViewSet, basename='mens-organization-testimonies')

# # URLs
# urlpatterns = [
#     # Main URLs and nested URLs
#     path('', include(router.urls)),
#     path('', include(member_router.urls)),
#     # path('', include(guestuser_router.urls)),
#     # path('', include(organization_router.urls)),
#     # path('', include(church_router.urls)),
#     # path('', include(mission_router.urls)),
#     # path('', include(publishing_house_router.urls)),
#     # path('', include(worship_ministry_router.urls)),
#     # path('', include(counseling_center_router.urls)),
#     # path('', include(conference_center_router.urls)),
#     # path('', include(institution_router.urls)),
#     # path('', include(children_org_router.urls)),
#     # path('', include(youth_org_router.urls)),
#     # path('', include(womens_org_router.urls)),
#     # path('', include(mens_org_router.urls)),

#     # Social Media Links
#     # path('', include(members_router.urls)),
#     # path('', include(organizations_router.urls)),
#     # path('', include(guestusers_router.urls)),

#     # Sanctuary related URLs
#     # path('', include(sanctuary_request_nested_router.urls)),
    
#     # Custom URLs for sanctuary history and appeal
#     # path('sanctuary-history/', SanctuaryHistoryViewSet.as_view({'get': 'list'}), name='sanctuary-history'),
#     # path('sanctuary-outcomes/<int:pk>/appeal/', SanctuaryOutcomeViewSet.as_view({'post': 'appeal'}), name='sanctuary-outcome-appeal'),

#     # Custom URLs for profiles and security actions
#     # path('members/<int:pk>/', MemberViewSet.as_view({'get': 'view_member_profile'})),
    
#     # path('members/profile/<str:username>/', MemberViewSet.as_view({'get': 'view_member_profile'}), name='profile-detail'),

#     # path('guestusers/<int:pk>/', GuestUserViewSet.as_view({'get': 'view_guest_profile'})),

#     # # Veriff Verification paths
#     # path('veriff/create/', VeriffViewSet.as_view({'post': 'create_verification_session'}), name='create-verification-session'),
#     # path('veriff/status/', VeriffViewSet.as_view({'get': 'get_verification_status'}), name='get-verification-status'),
    
#     # Design Tokens path
#     path('api/', include(router.urls)),  # http://127.0.0.1:8000/api/design-tokens/get_tokens/
# ]

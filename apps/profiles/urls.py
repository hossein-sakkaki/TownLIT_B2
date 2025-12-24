from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    MemberViewSet,
    GuestUserViewSet,
    ProfileMigrationViewSet,
    FriendshipViewSet,
    FellowshipViewSet,
    SpiritualGiftSurveyViewSet,
    SpiritualGiftSurveyQuestionViewSet,
    MemberSpiritualGiftsViewSet,
    MemberServicesViewSet,
    VisitorProfileViewSet,
)

# -------------------------------
# Router-registered viewsets (same style as before)
# -------------------------------
router = DefaultRouter()
router.register(r'members', MemberViewSet, basename='member')
router.register(r'guestusers', GuestUserViewSet, basename='guestuser')
router.register(r'migrate', ProfileMigrationViewSet, basename='profile-migration')
router.register(r'friendships', FriendshipViewSet, basename='friendship')
router.register(r'fellowship', FellowshipViewSet, basename='fellowship')
router.register(r'spiritual-gift', MemberSpiritualGiftsViewSet, basename='spiritual-gift')
router.register(r'spiritual-gift-survey-questions', SpiritualGiftSurveyQuestionViewSet, basename='spiritual-gift-survey-questions')
router.register(r'spiritual-gift-survey', SpiritualGiftSurveyViewSet, basename='spiritual-gift-survey')

# -------------------------------
# Map MemberServicesViewSet @actions explicitly (keeps BASE_PATH = /profiles/members)
# Using as_view to avoid router detail-route collisions and 405/404 issues.
# -------------------------------
services_catalog = MemberServicesViewSet.as_view({'get': 'services_catalog'})
my_services      = MemberServicesViewSet.as_view({'get': 'my_services'})
create_service   = MemberServicesViewSet.as_view({'post': 'create_service'})
detail_service   = MemberServicesViewSet.as_view({'patch': 'update_service', 'delete': 'delete_service'})
services_policy  = MemberServicesViewSet.as_view({'get': 'policy'})

# -------------------------------
# Custom paths (same pattern used elsewhere in the project)
# IMPORTANT: put these BEFORE router.urls in urlpatterns to prevent /members/<pk>/ from shadowing them.
# -------------------------------
custom_paths = [
    # existing custom endpoints
    path(
        'members/profile/<str:username>/',
        VisitorProfileViewSet.as_view({'get': 'profile'}),
        name='profile-detail'
    ),    
    path('guestusers/<int:pk>/',            
         GuestUserViewSet.as_view({'get': 'view_guest_profile'}), 
         name='guestuser-detail'),

    # member services (match frontend BASE_PATH = "/profiles/members")
    path('members/services-catalog/', services_catalog, name='member-services-catalog'),
    path('members/my-services/',      my_services,      name='member-my-services'),
    path('members/services/',         create_service,   name='member-services-create'),
    path('members/services/<int:pk>/', detail_service,  name='member-services-detail'),
    path('members/services-policy/',  services_policy,  name='member-services-policy'),
]

# Final URL patterns
urlpatterns = custom_paths + router.urls


from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    MemberViewSet,
    GuestUserViewSet,
    ProfileMigrationViewSet,
    FriendshipViewSet,
    FellowshipViewSet,
    VeriffViewSet,
    SpiritualGiftSurveyViewSet,
    SpiritualGiftSurveyQuestionViewSet,
    MemberSpiritualGiftsViewSet
)

# root router (بدون nested)
router = DefaultRouter()
router.register(r'members', MemberViewSet, basename='member')
router.register(r'guestusers', GuestUserViewSet, basename='guestuser')
router.register(r'migrate', ProfileMigrationViewSet, basename='profile-migration')
router.register(r'friendships', FriendshipViewSet, basename='friendship')
router.register(r'fellowship', FellowshipViewSet, basename='fellowship')
router.register(r'spiritual-gift', MemberSpiritualGiftsViewSet, basename='spiritual-gift')
router.register(r'spiritual-gift-survey-questions', SpiritualGiftSurveyQuestionViewSet, basename='spiritual-gift-survey-questions')
router.register(r'spiritual-gift-survey', SpiritualGiftSurveyViewSet, basename='spiritual-gift-survey')

# custom paths (مانند veriff و پروفایل عمومی)
custom_paths = [
    path('members/profile/<str:username>/', MemberViewSet.as_view({'get': 'view_member_profile'}), name='profile-detail'),
    path('guestusers/<int:pk>/', GuestUserViewSet.as_view({'get': 'view_guest_profile'}), name='guestuser-detail'),
    path('veriff/create/', VeriffViewSet.as_view({'post': 'create_verification_session'}), name='create-verification-session'),
    path('veriff/status/', VeriffViewSet.as_view({'get': 'get_verification_status'}), name='get-verification-status'),
]

# final
urlpatterns = router.urls + custom_paths

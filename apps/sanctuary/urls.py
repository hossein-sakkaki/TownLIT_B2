from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedSimpleRouter

from .views import (
    SanctuaryRequestViewSet,
    SanctuaryReviewViewSet,
    SanctuaryOutcomeViewSet,
    AdminSanctuaryReviewViewSet,
    SanctuaryHistoryViewSet
)

# Root router
router = DefaultRouter()
router.register(r'sanctuary-requests', SanctuaryRequestViewSet, basename='sanctuary-request')
router.register(r'sanctuary-reviews', SanctuaryReviewViewSet, basename='sanctuary-review')
router.register(r'sanctuary-outcomes', SanctuaryOutcomeViewSet, basename='sanctuary-outcome')
router.register(r'admin-sanctuary-reviews', AdminSanctuaryReviewViewSet, basename='admin-sanctuary-review')

# Nested: sanctuary-requests/<id>/reviews/
request_nested_router = NestedSimpleRouter(router, r'sanctuary-requests', lookup='sanctuary_request')
request_nested_router.register(r'reviews', SanctuaryReviewViewSet, basename='sanctuary-request-reviews')

# Custom paths
custom_paths = [
    path('sanctuary-history/', SanctuaryHistoryViewSet.as_view({'get': 'list'}), name='sanctuary-history'),
    path('sanctuary-outcomes/<int:pk>/appeal/', SanctuaryOutcomeViewSet.as_view({'post': 'appeal'}), name='sanctuary-outcome-appeal'),
]

# Combine all
urlpatterns = router.urls + request_nested_router.urls + custom_paths

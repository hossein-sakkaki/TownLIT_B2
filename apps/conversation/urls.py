from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DialogueViewSet, MessageViewSet, UserDialogueMarkerViewSet

router = DefaultRouter()
router.register(r'dialogues', DialogueViewSet, basename='dialogue')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'markers', UserDialogueMarkerViewSet, basename='marker')


app_name = 'conversation'
urlpatterns = [
    path('', include(router.urls)),
]

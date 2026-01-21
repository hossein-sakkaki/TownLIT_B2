# apps/translations/urls.py

from rest_framework.routers import SimpleRouter
from apps.translations.views.testimony import TestimonyTranslationViewSet
from apps.translations.views.moment import MomentTranslationViewSet
from apps.translations.views.languages import TranslationMetaViewSet

router = SimpleRouter()
router.register(
    r"testimonies",
    TestimonyTranslationViewSet,
    basename="translation-testimony",
)
router.register(
    r"moments",
    MomentTranslationViewSet,
    basename="translation-moment",
)
router.register(r"meta", TranslationMetaViewSet, basename="translation-meta")

urlpatterns = router.urls

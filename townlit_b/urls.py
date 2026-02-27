# apps/townlit_b/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.advancement.admin.site import advancement_admin_site 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ckeditor/', include('ckeditor_uploader.urls')),

    # Auth tokens (optionally move under /api/v1/auth/ later)
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # ✅ Versioned API gateway (single source of truth)
    path('api/v1/', include('api.v1.api_urls')),

    # Dedicated advancement admin
    path('advancement/', advancement_admin_site.urls),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
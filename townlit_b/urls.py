from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.main.views import coming_soon_view 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # path('', coming_soon_view),
    path('', include('apps.main.urls')),
    
    path('api/', include([
        path('', include('apps.main.urls')),
        
        path('accounts/', include('apps.accounts.urls')),
        path('profiles/', include('apps.profiles.urls')),
        path('profiles_org/', include('apps.profilesOrg.urls')),
        path('posts/', include('apps.posts.urls')),
        path('sanctuary/', include('apps.sanctuary.urls')),
        path('conversations/', include('apps.conversation.urls')),
        path('communication/', include('apps.communication.urls')),
        path('moderation/', include('apps.moderation.urls')),

        path('store/', include('apps.store.urls')),
        path('products/', include('apps.products.urls')),
        path('orders/', include('apps.orders.urls')),
        path('payment/', include('apps.payment.urls')),
        path('warehouse/', include('apps.warehouse.urls')),
        
        path('v1/', include('api.v1.api_urls')),
    ])),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
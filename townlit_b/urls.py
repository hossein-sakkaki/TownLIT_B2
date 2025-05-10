from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    

    
    path('', include('apps.main.urls')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('profiles/', include('apps.profiles.urls', namespace='profiles')),
    path('profiles_org/', include('apps.profilesOrg.urls', namespace='profiles_org')),
    path('posts/', include('apps.posts.urls', namespace='posts')),
    path('sanctuary/', include('apps.sanctuary.urls', namespace='sanctuary')),
    path('conversations/', include('apps.conversation.urls')),
    path('communication/', include('apps.communication.urls')),

    path('store/', include('apps.store.urls', namespace='store')),
    path('products/', include('apps.products.urls', namespace='products')),
    path('orders/', include('apps.orders.urls', namespace='orders')),
    path('payment/', include('apps.payment.urls', namespace='payment')),
    path('warehouse/', include('apps.warehouse.urls', namespace='warehouse')),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
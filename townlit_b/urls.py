"""townlit_b URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
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
    # path('conversation/', include('apps.conversation.urls', namespace='conversation')),
    path('conversations/', include('apps.conversation.urls')),  # مسیر درست برای conversation

    path('store/', include('apps.store.urls', namespace='store')),
    path('products/', include('apps.products.urls', namespace='products')),
    path('orders/', include('apps.orders.urls', namespace='orders')),
    path('payment/', include('apps.payment.urls', namespace='payment')),
    path('warehouse/', include('apps.warehouse.urls', namespace='warehouse')),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
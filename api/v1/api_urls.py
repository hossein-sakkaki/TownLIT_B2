# api/v1/api_urls.py
from django.urls import include, path


urlpatterns = [
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
    path('security/', include('apps.core.security.urls')),
]

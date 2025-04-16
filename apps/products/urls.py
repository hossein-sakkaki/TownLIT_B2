from django.urls import path, include

app_name = 'products'
urlpatterns = [
    path('', include('apps.store.urls')),
]
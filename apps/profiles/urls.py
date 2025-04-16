from django.urls import path, include

app_name = 'profiles'
urlpatterns = [
    path('', include('apps.main.urls')),
]
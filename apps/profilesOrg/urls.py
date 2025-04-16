from django.urls import path, include

app_name = 'profiles_org'
urlpatterns = [
    path('', include('apps.main.urls')),
]
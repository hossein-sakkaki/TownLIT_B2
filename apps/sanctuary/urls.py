from django.urls import path, include

app_name = 'sanctuary'
urlpatterns = [
    path('', include('apps.main.urls')),
]
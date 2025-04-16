from django.urls import path, include

app_name = 'warehouse'
urlpatterns = [
    path('', include('apps.store.urls', namespace='store')),
]

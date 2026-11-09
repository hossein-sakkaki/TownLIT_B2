# apps/ai_gateway/urls.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

from django.urls import path, re_path

from .views import denied_endpoint

app_name = "ai_gateway"
urlpatterns = [
    path("token/", denied_endpoint, name="token"),
    path("capabilities/", denied_endpoint, name="capabilities"),
    re_path(r"^.*$", denied_endpoint, name="denied"),
]

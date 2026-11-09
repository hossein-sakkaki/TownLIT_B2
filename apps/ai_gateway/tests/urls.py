# apps/ai_gateway/tests/urls.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

from django.urls import include, path

urlpatterns = [path("api/v1/ai-integrations/", include("apps.ai_gateway.urls"))]

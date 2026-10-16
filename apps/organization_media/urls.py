# apps/organization_media/urls.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-28.

from django.urls import path

from apps.organization_media.views import OrganizationMediaAssetViewSet


asset_list = OrganizationMediaAssetViewSet.as_view({
    "get": "list",
})

asset_detail = OrganizationMediaAssetViewSet.as_view({
    "get": "retrieve",
})


urlpatterns = [
    path(
        "organizations/<slug:slug>/assets/",
        asset_list,
        name="organization-media-assets",
    ),
    path(
        "organizations/<slug:slug>/assets/<uuid:public_id>/",
        asset_detail,
        name="organization-media-asset-detail",
    ),
]
# apps/organization_content/urls.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-10-20.

from django.urls import path

from apps.organization_content.views import (
    OrganizationContentBootstrapViewSet,
    OrganizationUpdateViewSet,
    PublicOrganizationFeedViewSet,
)


urlpatterns = [
    path(
        "system/bootstrap/",
        OrganizationContentBootstrapViewSet.as_view({
            "get": "list",
        }),
        name="organization-content-bootstrap",
    ),
    path(
        "<slug:slug>/feed/",
        PublicOrganizationFeedViewSet.as_view({
            "get": "list",
        }),
        name="organization-public-feed",
    ),
    path(
        "<slug:slug>/updates/",
        OrganizationUpdateViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
        name="organization-updates",
    ),
    path(
        "<slug:slug>/updates/<uuid:public_id>/",
        OrganizationUpdateViewSet.as_view({
            "get": "retrieve",
            "patch": "partial_update",
        }),
        name="organization-update-detail",
    ),
    path(
        "<slug:slug>/updates/<uuid:public_id>/submit/",
        OrganizationUpdateViewSet.as_view({"post": "submit"}),
        name="organization-update-submit",
    ),
    path(
        "<slug:slug>/updates/<uuid:public_id>/discard/",
        OrganizationUpdateViewSet.as_view({"delete": "discard"}),
        name="organization-update-discard",
    ),
    path(
        "<slug:slug>/updates/<uuid:public_id>/publish/",
        OrganizationUpdateViewSet.as_view({
            "post": "publish",
        }),
        name="organization-update-publish",
    ),
    path(
        "<slug:slug>/updates/<uuid:public_id>/archive/",
        OrganizationUpdateViewSet.as_view({
            "post": "archive",
        }),
        name="organization-update-archive",
    ),
    path(
        "<slug:slug>/updates/<uuid:public_id>/home-visibility/",
        OrganizationUpdateViewSet.as_view({
            "put": "home_visibility",
        }),
        name="organization-update-home-visibility",
    ),
]

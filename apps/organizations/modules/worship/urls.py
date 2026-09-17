# apps/organizations/modules/worship/urls.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-07.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from django.urls import path

from apps.organizations.modules.worship.views import (
    WorshipBootstrapView,
    WorshipContributionArtworkView,
    WorshipContributionAudioView,
    WorshipContributionCollectionView,
    WorshipContributionPublishView,
    WorshipContributionRevokeView,
    WorshipLicenseActivateView,
    WorshipLicenseCollectionView,
    WorshipLicenseEvidenceView,
    WorshipLicenseRevokeView,
    WorshipMusicChoicesView,
    WorshipRightsPartyCollectionView,
    WorshipRightsPartyDeactivateView,
)


urlpatterns = [
    path(
        "bootstrap/",
        WorshipBootstrapView.as_view(),
        name="worship-bootstrap",
    ),
    path(
        "rights-parties/",
        WorshipRightsPartyCollectionView.as_view(),
        name="worship-rights-parties",
    ),
    path(
        "rights-parties/<uuid:public_id>/deactivate/",
        WorshipRightsPartyDeactivateView.as_view(),
        name="worship-rights-party-deactivate",
    ),
    path(
        "licenses/",
        WorshipLicenseCollectionView.as_view(),
        name="worship-licenses",
    ),
    path(
        "licenses/<uuid:public_id>/evidence/",
        WorshipLicenseEvidenceView.as_view(),
        name="worship-license-evidence",
    ),
    path(
        "licenses/<uuid:public_id>/activate/",
        WorshipLicenseActivateView.as_view(),
        name="worship-license-activate",
    ),
    path(
        "licenses/<uuid:public_id>/revoke/",
        WorshipLicenseRevokeView.as_view(),
        name="worship-license-revoke",
    ),
    path(
        "contributions/",
        WorshipContributionCollectionView.as_view(),
        name="worship-contributions",
    ),
    path(
        "contributions/<uuid:public_id>/artwork/",
        WorshipContributionArtworkView.as_view(),
        name="worship-contribution-artwork",
    ),
    path(
        "contributions/<uuid:public_id>/audio/",
        WorshipContributionAudioView.as_view(),
        name="worship-contribution-audio",
    ),
    path(
        "contributions/<uuid:public_id>/publish/",
        WorshipContributionPublishView.as_view(),
        name="worship-contribution-publish",
    ),
    path(
        "contributions/<uuid:public_id>/revoke/",
        WorshipContributionRevokeView.as_view(),
        name="worship-contribution-revoke",
    ),
    path(
        "choices/",
        WorshipMusicChoicesView.as_view(),
        name="worship-music-choices",
    ),
]
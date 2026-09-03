# apps/organizations/modules/worship/selectors/music.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from apps.organizations.modules.worship.constants import WorshipPermissionKey
from apps.organizations.modules.worship.models import OrganizationMusicContribution, OrganizationMusicLicense
from apps.organizations.modules.worship.services.access import ensure_worship_permission


def list_organization_music_licenses(*, workspace, actor):
    ensure_worship_permission(actor=actor, workspace=workspace, permission_key=WorshipPermissionKey.VIEW_MUSIC, require_write=False)
    return OrganizationMusicLicense.objects.filter(workspace=workspace).select_related("licensor__rights_party", "master_owner__rights_party", "composition_owner__rights_party").order_by("-created_at", "-id")


def list_organization_music_contributions(*, workspace, actor):
    ensure_worship_permission(actor=actor, workspace=workspace, permission_key=WorshipPermissionKey.VIEW_MUSIC, require_write=False)
    return OrganizationMusicContribution.objects.filter(workspace=workspace).select_related("license", "track", "primary_artist", "rights_record").order_by("-created_at", "-id")

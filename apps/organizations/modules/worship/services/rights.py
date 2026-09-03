# apps/organizations/modules/worship/services/rights.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audio_catalog.models import RightsParty
from apps.organizations.modules.worship.constants import WorshipAuditEvent, WorshipPermissionKey
from apps.organizations.modules.worship.models import OrganizationRightsParty
from .access import ensure_worship_permission
from .audit import record_worship_audit


@transaction.atomic
def create_organization_rights_party(*, workspace, actor, display_name, kind=RightsParty.Kind.ORGANIZATION, legal_name="", country_code="", website_url="", contact_email="", external_reference="", relationship="other", metadata=None):
    ensure_worship_permission(actor=actor, workspace=workspace, permission_key=WorshipPermissionKey.MANAGE_RIGHTS)
    display_name = str(display_name or "").strip()
    if not display_name:
        raise ValidationError({"display_name": "Rights party display name is required."})
    party = RightsParty.objects.create(display_name=display_name, legal_name=str(legal_name or "").strip(), kind=kind, country_code=str(country_code or "").strip().upper(), website_url=str(website_url or "").strip(), contact_email=str(contact_email or "").strip(), external_reference=str(external_reference or "").strip(), metadata=metadata or {})
    link = OrganizationRightsParty.objects.create(workspace=workspace, rights_party=party, relationship=relationship)
    record_worship_audit(workspace=workspace, event=WorshipAuditEvent.RIGHTS_PARTY_LINKED, actor=actor, entity=link, metadata={"rights_party_public_id": str(party.public_id), "relationship": relationship})
    return link


@transaction.atomic
def deactivate_organization_rights_party(*, link, actor):
    locked = OrganizationRightsParty.objects.select_for_update().select_related("workspace").get(pk=link.pk)
    ensure_worship_permission(actor=actor, workspace=locked.workspace, permission_key=WorshipPermissionKey.MANAGE_RIGHTS)
    if not locked.is_active:
        return locked
    if locked.licenses_as_licensor.filter(status="active").exists() or locked.licenses_as_master_owner.filter(status="active").exists() or locked.licenses_as_composition_owner.filter(status="active").exists():
        raise ValidationError("Rights party is referenced by an active music license.")
    locked.is_active = False
    locked.save(update_fields=["is_active", "updated_at"])
    record_worship_audit(workspace=locked.workspace, event=WorshipAuditEvent.RIGHTS_PARTY_DEACTIVATED, actor=actor, entity=locked)
    return locked

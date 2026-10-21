# apps/organizations/services/profile_details.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-10-20.
#

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.db import transaction
from django.utils import timezone

from apps.accounts.models.social import (
    SocialMediaLink,
)
from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationMembershipStatus,
    OrganizationPermissionKey,
    OrganizationRepresentativeStatus,
)
from apps.organizations.models import (
    Organization,
    OrganizationAuditLog,
    OrganizationBusinessHour,
    OrganizationContactPoint,
    OrganizationMembership,
    OrganizationRepresentative,
)
from apps.organizations.services.access import (
    user_has_organization_permission,
)
from apps.organizations.services.lifecycle_policy import (
    require_operational_organization,
)


def _ensure_profile_manager(
    *,
    organization,
    actor,
):
    require_operational_organization(organization=organization)

    if not user_has_organization_permission(
        user=actor,
        organization=organization,
        permission_key=(
            OrganizationPermissionKey
            .MANAGE_PROFILE
        ),
    ):
        raise PermissionDenied(
            "You do not have permission to "
            "manage this organization profile."
        )


def _record_change(
    *,
    organization,
    actor,
    section,
    metadata=None,
):
    OrganizationAuditLog.objects.create(
        organization=organization,
        action=(
            OrganizationAuditAction
            .ORGANIZATION_UPDATED
        ),
        source=(
            OrganizationAuditSource
            .SERVICE
        ),
        actor=actor,
        metadata={
            "section": section,
            **(
                metadata
                or {}
            ),
        },
    )


@transaction.atomic
def create_contact_point(
    *,
    organization,
    actor,
    validated_data,
):
    _ensure_profile_manager(
        organization=organization,
        actor=actor,
    )

    contact = OrganizationContactPoint(
        organization=organization,
        **validated_data,
    )

    contact.full_clean()
    contact.save()

    if contact.is_primary:
        (
            OrganizationContactPoint.objects
            .filter(
                organization=organization,
                channel=contact.channel,
            )
            .exclude(
                pk=contact.pk
            )
            .update(
                is_primary=False
            )
        )

    _record_change(
        organization=organization,
        actor=actor,
        section="contact_points",
        metadata={
            "action": "created",
            "contact_public_id": str(
                contact.public_id
            ),
            "channel": contact.channel,
        },
    )

    return contact


@transaction.atomic
def update_contact_point(
    *,
    contact,
    actor,
    validated_data,
):
    contact = (
        OrganizationContactPoint.objects
        .select_for_update()
        .select_related(
            "organization"
        )
        .get(
            pk=contact.pk
        )
    )

    _ensure_profile_manager(
        organization=contact.organization,
        actor=actor,
    )

    for field, value in (
        validated_data.items()
    ):
        setattr(
            contact,
            field,
            value,
        )

    contact.full_clean()
    contact.save()

    if contact.is_primary:
        (
            OrganizationContactPoint.objects
            .filter(
                organization=contact.organization,
                channel=contact.channel,
            )
            .exclude(
                pk=contact.pk
            )
            .update(
                is_primary=False
            )
        )

    _record_change(
        organization=contact.organization,
        actor=actor,
        section="contact_points",
        metadata={
            "action": "updated",
            "contact_public_id": str(
                contact.public_id
            ),
        },
    )

    return contact


@transaction.atomic
def delete_contact_point(
    *,
    contact,
    actor,
):
    organization = contact.organization

    _ensure_profile_manager(
        organization=organization,
        actor=actor,
    )

    public_id = str(
        contact.public_id
    )

    contact.delete()

    _record_change(
        organization=organization,
        actor=actor,
        section="contact_points",
        metadata={
            "action": "deleted",
            "contact_public_id": public_id,
        },
    )


_MINUTES_PER_DAY = 24 * 60
_MINUTES_PER_WEEK = 7 * _MINUTES_PER_DAY


def _clock_minutes(value):
    return value.hour * 60 + value.minute + (value.second / 60)


def _validate_weekly_business_hours(rows):
    """Validate the complete weekly timetable before replacing any rows.

    Overnight intervals end on the next day. Monday-to-Sunday boundaries
    are treated as circular so a late Sunday shift cannot overlap Monday.
    """
    by_day = {day: [] for day in range(7)}
    reserved_slots = set()
    windows = []

    for row in rows:
        if row.weekday not in by_day:
            raise ValidationError({"weekday": "Weekday must be between 0 and 6."})
        slot = (row.weekday, row.sort_order)
        if slot in reserved_slots:
            raise ValidationError({
                "sort_order": "Each weekday requires unique sort_order values."
            })
        reserved_slots.add(slot)
        by_day[row.weekday].append(row)

    for weekday, daily_rows in by_day.items():
        special = [row for row in daily_rows if row.is_closed or row.is_24_hours]
        if special and len(daily_rows) != 1:
            raise ValidationError({
                "weekday": (
                    f"Day {weekday} cannot mix Closed/24 Hours "
                    "with other business-hour intervals."
                )
            })
        if not daily_rows:
            continue
        for row in daily_rows:
            if row.is_closed:
                continue
            if row.is_24_hours:
                start = weekday * _MINUTES_PER_DAY
                end = start + _MINUTES_PER_DAY
            else:
                start = weekday * _MINUTES_PER_DAY + _clock_minutes(row.opens_at)
                end = weekday * _MINUTES_PER_DAY + _clock_minutes(row.closes_at)
                if end < start:
                    end += _MINUTES_PER_DAY
                    following_day = (weekday + 1) % 7
                    if any(day.is_closed for day in by_day[following_day]):
                        raise ValidationError({
                            "weekday": (
                                f"Overnight hours on day {weekday} "
                                f"conflict with Closed day {following_day}."
                            )
                        })
            windows.append((start, end, weekday))

    # All windows are shorter than or equal to 24 hours. Checking a single
    # neighboring weekly translation covers Sunday -> Monday boundaries.
    for index, (first_start, first_end, _) in enumerate(windows):
        for second_start, second_end, _ in windows[index + 1:]:
            for week_shift in (-_MINUTES_PER_WEEK, 0, _MINUTES_PER_WEEK):
                shifted_start = second_start + week_shift
                shifted_end = second_end + week_shift
                if first_start < shifted_end and shifted_start < first_end:
                    raise ValidationError({
                        "weekday": "Business-hour intervals cannot overlap."
                    })


@transaction.atomic
def replace_business_hours(
    *,
    organization,
    actor,
    validated_rows,
):
    _ensure_profile_manager(
        organization=organization,
        actor=actor,
    )

    # Validate the full proposed schedule before deleting the old one.
    rows = []
    for data in validated_rows:
        row = OrganizationBusinessHour(
            organization=organization,
            **data,
        )
        # Old rows still exist at this point. The service checks uniqueness
        # for the proposed replacement set; do not compare against old slots.
        row.full_clean(validate_unique=False, validate_constraints=False)
        rows.append(row)

    _validate_weekly_business_hours(rows)

    OrganizationBusinessHour.objects.filter(
        organization=organization,
    ).delete()

    OrganizationBusinessHour.objects.bulk_create(rows)

    _record_change(
        organization=organization,
        actor=actor,
        section="business_hours",
        metadata={
            "action": "replaced",
            "rows": len(rows),
        },
    )

    return OrganizationBusinessHour.objects.filter(
        organization=organization,
    ).order_by("weekday", "sort_order", "id")


@transaction.atomic
def invite_representative(
    *,
    organization,
    actor,
    membership_public_id,
    role_title,
    is_primary=False,
    sort_order=0,
):
    _ensure_profile_manager(
        organization=organization,
        actor=actor,
    )

    try:
        membership = (
            OrganizationMembership.objects
            .select_related(
                "member__user"
            )
            .get(
                public_id=membership_public_id,
                organization=organization,
                status=(
                    OrganizationMembershipStatus
                    .ACTIVE
                ),
            )
        )

    except OrganizationMembership.DoesNotExist:
        raise ValidationError({
            "membership_public_id": (
                "An active organization membership "
                "was not found."
            ),
        })

    representative, created = (
        OrganizationRepresentative.objects
        .select_for_update()
        .get_or_create(
            organization=organization,
            membership=membership,
            defaults={
                "role_title": role_title,
                "status": (
                    OrganizationRepresentativeStatus
                    .PENDING
                ),
                "is_primary": is_primary,
                "sort_order": sort_order,
                "invited_by": actor,
            },
        )
    )

    if not created:
        representative.role_title = (
            role_title
        )

        representative.is_primary = (
            is_primary
        )

        representative.sort_order = (
            sort_order
        )

        representative.invited_by = actor

        if representative.status in {
            OrganizationRepresentativeStatus.DECLINED,
            OrganizationRepresentativeStatus.REMOVED,
        }:
            representative.status = (
                OrganizationRepresentativeStatus
                .PENDING
            )

            representative.responded_at = None

    representative.full_clean()
    representative.save()

    if representative.is_primary:
        (
            OrganizationRepresentative.objects
            .filter(
                organization=organization
            )
            .exclude(
                pk=representative.pk
            )
            .update(
                is_primary=False
            )
        )

    _record_change(
        organization=organization,
        actor=actor,
        section="representatives",
        metadata={
            "action": (
                "created"
                if created
                else "updated"
            ),
            "representative_public_id": str(
                representative.public_id
            ),
            "membership_public_id": str(
                membership.public_id
            ),
        },
    )

    return representative


@transaction.atomic
def respond_to_representative_invitation(
    *,
    representative,
    actor,
    decision,
):
    representative = (
        OrganizationRepresentative.objects
        .select_for_update()
        .select_related(
            "organization",
            "membership__member__user",
        )
        .get(
            pk=representative.pk
        )
    )

    require_operational_organization(organization=representative.organization)

    if (
        representative
        .membership
        .member
        .user_id
        != actor.id
    ):
        raise PermissionDenied(
            "Only the invited member can "
            "respond to this request."
        )

    if (
        representative.status
        != OrganizationRepresentativeStatus.PENDING
    ):
        raise ValidationError(
            "This representative invitation "
            "is no longer pending."
        )

    if (
        decision
        == OrganizationRepresentativeStatus.ACCEPTED
        and representative.membership.status
        != OrganizationMembershipStatus.ACTIVE
    ):
        raise ValidationError(
            "An active organization membership "
            "is required."
        )

    representative.status = decision
    representative.responded_at = timezone.now()

    representative.full_clean()
    representative.save(
        update_fields=[
            "status",
            "responded_at",
            "updated_at",
        ]
    )

    _record_change(
        organization=representative.organization,
        actor=actor,
        section="representatives",
        metadata={
            "action": decision,
            "representative_public_id": str(
                representative.public_id
            ),
        },
    )

    return representative


@transaction.atomic
def remove_representative(
    *,
    representative,
    actor,
):
    representative = (
        OrganizationRepresentative.objects
        .select_for_update()
        .select_related(
            "organization",
            "membership__member__user",
        )
        .get(
            pk=representative.pk
        )
    )

    is_self = (
        representative
        .membership
        .member
        .user_id
        == actor.id
    )

    can_manage = (
        user_has_organization_permission(
            user=actor,
            organization=(
                representative.organization
            ),
            permission_key=(
                OrganizationPermissionKey
                .MANAGE_PROFILE
            ),
        )
    )

    if not (
        is_self
        or can_manage
    ):
        raise PermissionDenied(
            "You cannot remove this "
            "public representative."
        )

    representative.status = (
        OrganizationRepresentativeStatus
        .REMOVED
    )

    representative.is_primary = False
    representative.responded_at = timezone.now()

    representative.save(
        update_fields=[
            "status",
            "is_primary",
            "responded_at",
            "updated_at",
        ]
    )

    _record_change(
        organization=representative.organization,
        actor=actor,
        section="representatives",
        metadata={
            "action": "removed",
            "representative_public_id": str(
                representative.public_id
            ),
        },
    )

    return representative


def _organization_content_type():
    return (
        ContentType.objects
        .get_for_model(
            Organization,
            for_concrete_model=False,
        )
    )


@transaction.atomic
def create_social_link(
    *,
    organization,
    actor,
    social_media_type,
    link,
    is_active=True,
):
    _ensure_profile_manager(
        organization=organization,
        actor=actor,
    )

    content_type = (
        _organization_content_type()
    )

    if (
        SocialMediaLink.objects
        .filter(
            content_type=content_type,
            object_id=organization.pk,
            social_media_type=(
                social_media_type
            ),
        )
        .exists()
    ):
        raise ValidationError({
            "social_media_type": (
                "A link for this social media "
                "type already exists."
            ),
        })

    social_link = SocialMediaLink(
        social_media_type=(
            social_media_type
        ),
        link=link,
        is_active=is_active,
        content_type=content_type,
        object_id=organization.pk,
    )

    social_link.full_clean()
    social_link.save()

    _record_change(
        organization=organization,
        actor=actor,
        section="social_links",
        metadata={
            "action": "created",
            "social_link_id": social_link.pk,
        },
    )

    return social_link


@transaction.atomic
def update_social_link(
    *,
    organization,
    actor,
    social_link,
    validated_data,
):
    _ensure_profile_manager(
        organization=organization,
        actor=actor,
    )

    content_type = (
        _organization_content_type()
    )

    social_link = (
        SocialMediaLink.objects
        .select_for_update()
        .get(
            pk=social_link.pk,
            content_type=content_type,
            object_id=organization.pk,
        )
    )

    for field in (
        "link",
        "is_active",
    ):
        if field in validated_data:
            setattr(
                social_link,
                field,
                validated_data[field],
            )

    social_link.full_clean()
    social_link.save()

    _record_change(
        organization=organization,
        actor=actor,
        section="social_links",
        metadata={
            "action": "updated",
            "social_link_id": social_link.pk,
        },
    )

    return social_link


@transaction.atomic
def delete_social_link(
    *,
    organization,
    actor,
    social_link,
):
    _ensure_profile_manager(
        organization=organization,
        actor=actor,
    )

    social_link_id = (
        social_link.pk
    )

    social_link.delete()

    _record_change(
        organization=organization,
        actor=actor,
        section="social_links",
        metadata={
            "action": "deleted",
            "social_link_id": social_link_id,
        },
    )

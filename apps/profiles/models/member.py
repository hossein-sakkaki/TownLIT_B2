# apps/profiles/models/member.py

from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.posts.models.testimony import Testimony
from apps.profiles.models.academic import AcademicRecord
from apps.profiles.models.services import MemberServiceType
from apps.profilesOrg.constants_denominations import (
    CHURCH_BRANCH_CHOICES,
    CHURCH_FAMILY_CHOICES_ALL,
    FAMILIES_BY_BRANCH,
)
from utils.common.utils import FileUpload, SlugMixin
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


class Member(SlugMixin):
    FILE = FileUpload("profiles", "file", "member")

    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="member_profile",
        verbose_name="User",
    )

    service_types = models.ManyToManyField(
        MemberServiceType,
        blank=True,
        db_index=True,
        related_name="member_service_types",
        verbose_name="Service Types",
    )
    organization_memberships = models.ManyToManyField(
        "profilesOrg.Organization",
        blank=True,
        db_index=True,
        related_name="memberships",
        verbose_name="Organization Memberships",
    )

    biography = models.CharField(max_length=2000, null=True, blank=True, verbose_name="Biography")
    vision = models.CharField(max_length=2000, null=True, blank=True, verbose_name="Vision")
    spiritual_rebirth_day = models.DateField(
        auto_now=False,
        auto_now_add=False,
        null=True,
        blank=True,
        verbose_name="Spiritual Rebirth Days",
    )
    academic_record = models.OneToOneField(
        AcademicRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="member_academic_record",
    )

    denomination_branch = models.CharField(
        max_length=40,
        choices=CHURCH_BRANCH_CHOICES,
        null=False,
        blank=False,
        verbose_name="Denomination Branch",
    )
    denomination_family = models.CharField(
        max_length=60,
        choices=CHURCH_FAMILY_CHOICES_ALL,
        null=True,
        blank=True,
        verbose_name="Denomination Family (Optional)",
    )

    show_gifts_in_profile = models.BooleanField(
        default=True,
        verbose_name="Show Gifts in Profile",
        help_text="Allow gifts to be visible on the profile page.",
    )
    show_fellowship_in_profile = models.BooleanField(
        default=True,
        verbose_name="Show Fellowship in Profile",
    )
    hide_confidants = models.BooleanField(default=False, verbose_name="Hide Confidants in setting")

    testimonies = GenericRelation(
        Testimony,
        related_query_name="owner_member",
        content_type_field="content_type",
        object_id_field="object_id",
    )

    register_date = models.DateField(default=timezone.localdate, verbose_name='Register Date')

    is_townlit_verified = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="TownLIT Verified",
    )
    townlit_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="TownLIT Verified At",
    )
    townlit_verified_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="TownLIT Verification Reason",
    )

    is_hidden_by_confidants = models.BooleanField(default=False, verbose_name="Hidden by Confidants")
    is_privacy = models.BooleanField(default=False, verbose_name="Is Privacy")
    is_migrated = models.BooleanField(default=False, verbose_name="Is Migrated")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    url_name = "member_detail"

    class Meta:
        verbose_name = "1. Member"
        verbose_name_plural = "1. Members"

    def __str__(self):
        return self.user.username

    def get_slug_source(self):
        return self.user.username

    def is_manager(self):
        return self.organization_adminships.exists()

    def managed_organizations(self):
        return self.organization_adminships.all()

    def clean(self):
        # Ensure selected family belongs to selected branch.
        branch = self.denomination_branch
        family = self.denomination_family

        if family and branch:
            allowed = FAMILIES_BY_BRANCH.get(branch, set())
            if family not in allowed:
                raise ValidationError(
                    {
                        "denomination_family": (
                            "Selected family does not belong to the chosen branch."
                        )
                    }
                )
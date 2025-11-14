from django.db import models
from django.utils import timezone 
from django.urls import reverse
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericRelation
from apps.accounts.models import Address
from django.core.exceptions import ValidationError
from apps.posts.models import Testimony
from apps.profilesOrg.constants import CHURCH_DENOMINATIONS_CHOICES
from apps.profilesOrg.constants_denominations import CHURCH_BRANCH_CHOICES, CHURCH_FAMILY_CHOICES_ALL, FAMILIES_BY_BRANCH
from apps.profiles.gift_constants import GIFT_CHOICES, GIFT_DESCRIPTIONS, GIFT_LANGUAGE_CHOICES, ANSWER_CHOICES
from .constants import (
                            FRIENDSHIP_STATUS_CHOICES, EDUCATION_DOCUMENT_TYPE_CHOICES, 
                            EDUCATION_DEGREE_CHOICES, MIGRATION_CHOICES,
                            IDENTITY_VERIFICATION_STATUS_CHOICES, NOT_SUBMITTED,
                            CUSTOMER_DEACTIVATION_REASON_CHOICES,
                            FELLOWSHIP_RELATIONSHIP_CHOICES, RECIPROCAL_FELLOWSHIP_CHOICES, FELLOWSHIP_STATUS_CHOICES,
                            STANDARD_MINISTRY_CHOICES,
                        )
from validators.user_validators import validate_phone_number
from validators.mediaValidators.pdf_validators import validate_pdf_file
from validators.security_validators import validate_no_executable_file

from utils.common.utils import FileUpload, SlugMixin
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# FRIENDSHIP Manager -----------------------------------------------------------------------------------
class Friendship(models.Model):
    id = models.BigAutoField(primary_key=True)
    from_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, db_index=True, related_name='friendships_initiated', verbose_name="Initiator")
    to_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, db_index=True, related_name='friendships_received', verbose_name="Friend")
    status = models.CharField(max_length=20, choices=FRIENDSHIP_STATUS_CHOICES, default='pending', verbose_name='Status')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Created At')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Deleted At')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['from_user', 'to_user'],
                condition=models.Q(is_active=True),
                name='unique_active_friendship'
            )
        ]
        verbose_name = 'Friendship'
        verbose_name_plural = 'Friendships'

    def __str__(self):
        return f"{self.from_user.username} to {self.to_user.username} ({self.status})"

    def get_absolute_url(self):
        """
        Returns the appropriate frontend URL for Friendship notifications.

        - Pending → opens the 'Requests' tab in Friendship settings page.
        - Accepted → opens the other user's public profile.
        - Declined → opens the other user's public profile.
        - Cancelled/Deleted → also opens the other user's public profile (the actor).
        """
        try:
            # 🔹 Pending friend request → open requests tab
            if self.status == "pending":
                return "/settings/friendships?tab=requests"

            # 🔹 For all other statuses → show the *other* user's profile
            # figure out who should be shown depending on who triggered the action
            actor = getattr(self, "from_user", None)
            target = getattr(self, "to_user", None)

            # If the friendship was deleted or cancelled, show actor's profile
            if self.status in ["deleted", "cancelled"]:
                if actor:
                    return f"/lit/{actor.username}"

            # Otherwise (accepted / declined), show the other person’s profile
            if target:
                return f"/lit/{target.username}"

            # fallback safety
            return "/lit/"

        except Exception:
            return "/lit/"

    
    
# FELLOWSHIP Manager -----------------------------------------------------------------------------------    
class Fellowship(models.Model):
    id = models.BigAutoField(primary_key=True)
    from_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='fellowship_sent', verbose_name=_('From User'))
    to_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='fellowship_received', verbose_name=_('To User'))
    fellowship_type = models.CharField(max_length=20, choices=FELLOWSHIP_RELATIONSHIP_CHOICES, verbose_name=_('Fellowship Type'))
    reciprocal_fellowship_type = models.CharField(max_length=50, choices=RECIPROCAL_FELLOWSHIP_CHOICES, null=True, blank=True, verbose_name=_('Reciprocal Fellowship Type'))
    status = models.CharField(max_length=20, choices=FELLOWSHIP_STATUS_CHOICES, default='Pending', verbose_name=_('Status'))
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_('Created At'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Fellowship')
        verbose_name_plural = _('Fellowships')
        constraints = [
            models.UniqueConstraint(
                fields=['from_user', 'to_user', 'fellowship_type', 'reciprocal_fellowship_type'],
                name='unique_fellowship_per_type'
            )
        ]

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} ({self.fellowship_type})"

    def get_absolute_url(self):
        """
        Returns the correct frontend route for Fellowship notifications.
        - Pending → settings covenant page
        - Accepted/Declined → profile of the other user
        - Cancelled → profile of the actor (who removed the fellowship)
        """
        try:
            if self.status == "Pending":
                return "/settings/lit-covenant"

            # For cancelled relationships → show actor's profile
            if self.status == "Cancelled":
                if hasattr(self, "from_user") and self.from_user:
                    return f"/lit/{self.from_user.username}"

            # For other finalized statuses → show the other user's profile
            if hasattr(self, "to_user") and self.to_user:
                return f"/lit/{self.to_user.username}"

            return "/lit/"
        except Exception:
            return "/lit/"




# ACADEMIC RECORD Manager --------------------------------------------------------------------------------
class StudyStatus(models.TextChoices):
    IN_PROGRESS = "in_progress", _("In Progress")
    COMPLETED   = "completed",   _("Completed")
    ON_HOLD     = "on_hold",     _("On Hold")
    DROPPED     = "dropped",     _("Dropped")

class AcademicRecord(models.Model):
    DOCUMENT = FileUpload('profiles', 'documents', 'academic_record')

    id = models.BigAutoField(primary_key=True)
    education_document_type = models.CharField(
        max_length=50, choices=EDUCATION_DOCUMENT_TYPE_CHOICES,
        verbose_name='Education Document Type'
    )
    education_degree = models.CharField(
        max_length=100, choices=EDUCATION_DEGREE_CHOICES,
        verbose_name='Education Degree'
    )
    school = models.CharField(max_length=100, verbose_name='School')
    country = models.CharField(max_length=100, verbose_name='Country')

    started_at = models.DateField(null=True, blank=True, verbose_name='Started At (YYYY-MM-01)')
    expected_graduation_at = models.DateField(null=True, blank=True, verbose_name='Expected Graduation (YYYY-MM-01)')
    graduated_at = models.DateField(null=True, blank=True, verbose_name='Graduated At (YYYY-MM-01)')
    status = models.CharField(
        max_length=20, choices=StudyStatus.choices, default=StudyStatus.IN_PROGRESS,
        verbose_name='Study Status'
    )
    document = models.FileField(
        upload_to=DOCUMENT.dir_upload, null=True, blank=True,
        validators=[validate_pdf_file, validate_no_executable_file],
        verbose_name='Document'
    )

    is_theology_related = models.BooleanField(default=False, verbose_name='Theology Related')
    is_approved = models.BooleanField(default=False, verbose_name='Is Approved')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    class Meta:
        verbose_name = "Academic Record"
        verbose_name_plural = "Academic Records"
        ordering = ['-started_at', '-graduated_at', '-expected_graduation_at', '-id']

    def __str__(self):
        return f"{self.education_degree}"

    def get_absolute_url(self):
        return reverse("academic_record_detail", kwargs={"pk": self.pk})

    # ── Helpers ───────────────────────────────────────────
    @staticmethod
    def _ensure_first_of_month(value):
        """If a Date is provided, force day=1 (we keep month-level precision)."""
        if value and value.day != 1:
            return value.replace(day=1)
        return value

    def clean(self):
        errors = {}

        # Normalize to day=1 (month-level precision)
        self.started_at = self._ensure_first_of_month(self.started_at)
        self.expected_graduation_at = self._ensure_first_of_month(self.expected_graduation_at)
        self.graduated_at = self._ensure_first_of_month(self.graduated_at)

        # Temporal order checks
        if self.started_at and self.expected_graduation_at:
            if self.expected_graduation_at < self.started_at:
                errors["expected_graduation_at"] = _("Expected graduation cannot be before start date.")
        if self.started_at and self.graduated_at:
            if self.graduated_at < self.started_at:
                errors["graduated_at"] = _("Graduation date cannot be before start date.")

        # Status logic
        if self.status == StudyStatus.COMPLETED:
            # Completed requires graduated_at; expected is optional (but should be ≤ graduated_at if present)
            if not self.graduated_at:
                errors["graduated_at"] = _("Graduated date is required when status is 'Completed'.")
        elif self.status == StudyStatus.IN_PROGRESS:
            # In progress should NOT have graduated_at
            if self.graduated_at:
                errors["graduated_at"] = _("Remove graduation date for 'In Progress' status.")
        elif self.status == StudyStatus.DROPPED:
            # Dropped shouldn't have a graduation date
            if self.graduated_at:
                errors["graduated_at"] = _("Do not set graduation date when status is 'Dropped'.")
        # ON_HOLD: no strict extra rule

        if errors:
            raise ValidationError(errors)

    @property
    def period_display(self) -> str:
        """Human-friendly period for UI, e.g. '2021 Sep – present (expected 2025 Jun)'."""
        def ym(d):
            return d.strftime("%Y %b") if d else "—"
        if self.status == StudyStatus.IN_PROGRESS:
            start = ym(self.started_at)
            exp = ym(self.expected_graduation_at) if self.expected_graduation_at else None
            tail = f" (expected {exp})" if exp else ""
            return f"{start} – present{tail}"
        if self.status == StudyStatus.COMPLETED and self.started_at and self.graduated_at:
            return f"{ym(self.started_at)} – {ym(self.graduated_at)}"
        if self.status == StudyStatus.DROPPED:
            # اگر شروع داشته ولی قطع شده (بدون graduation)
            base = f"{ym(self.started_at)} – dropped"
            return base
        if self.status == StudyStatus.ON_HOLD:
            base = f"{ym(self.started_at)} – on hold"
            if self.expected_graduation_at:
                base += f" (expected {ym(self.expected_graduation_at)})"
            return base
        # fallback
        if self.graduated_at:
            return f"graduated {ym(self.graduated_at)}"
        if self.started_at:
            return f"since {ym(self.started_at)}"
        return "—"


# Migration History --------------------------------------------------------------------------------------
class MigrationHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='migration_history')
    migration_type = models.CharField(max_length=20, choices=MIGRATION_CHOICES)
    migration_date = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = "Migration History"
        verbose_name_plural = "Migration Histories"

    def __str__(self):
        return f'{self.user.username} - {self.migration_type} on {self.migration_date}'


# Spiritual Service ---------------------------------------------------------------------------------------
class SpiritualService(models.Model):
    name = models.CharField(max_length=40, choices=STANDARD_MINISTRY_CHOICES, unique=True, verbose_name="Name of Service")
    description = models.CharField(max_length=300, null=True, blank=True, verbose_name="Description")
    is_sensitive = models.BooleanField(default=False, verbose_name="Requires Credential")  # 👈 NEW
    is_active = models.BooleanField(default=True, verbose_name="Is Active")

    class Meta:
        verbose_name = "Spiritual Service"
        verbose_name_plural = "Spiritual Services"

    def __str__(self):
        return self.name

# Member Service Type ---------------------------------------------------------------------------------------
class MemberServiceType(models.Model):
    class Status(models.TextChoices):
        PENDING  = "pending",  "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ACTIVE   = "active",   "Active (no approval needed)" 

    DOCUMENT = FileUpload("profiles", "documents", "member_service_type")

    id = models.BigAutoField(primary_key=True)
    service = models.ForeignKey(SpiritualService, on_delete=models.CASCADE, related_name="service_instances")
    history = models.CharField(max_length=500, null=True, blank=True)
    document = models.FileField(
        upload_to=DOCUMENT.dir_upload, blank=True, null=True,
        validators=[validate_pdf_file, validate_no_executable_file]
    )

    # credential metadata
    credential_issuer = models.CharField(max_length=120, null=True, blank=True)
    credential_number = models.CharField(max_length=80, null=True, blank=True)
    credential_url    = models.URLField(null=True, blank=True)
    issued_at         = models.DateField(null=True, blank=True)
    expires_at        = models.DateField(null=True, blank=True)

    # review flow
    status      = models.CharField(max_length=16, choices=Status.choices, db_index=True)
    review_note = models.CharField(max_length=300, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)

    # misc
    register_date = models.DateField(auto_now_add=True)
    is_active     = models.BooleanField(default=True)

    class Meta:
        verbose_name = "MemberServiceType"
        verbose_name_plural = "MemberServiceTypes"

    def __str__(self):
        return self.service.name

              

# Member Manager -------------------------------------------------------------------------------------------
class Member(SlugMixin):
    FILE = FileUpload('profiles', 'file', 'member')

    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="member_profile", verbose_name='User')
        
    service_types = models.ManyToManyField(MemberServiceType, blank=True, db_index=True, related_name='member_service_types', verbose_name='Service Types')
    organization_memberships = models.ManyToManyField('profilesOrg.Organization', blank=True, db_index=True, related_name='memberships', verbose_name='Organization Memberships')
    
    biography = models.CharField(max_length=1000, null=True, blank=True, verbose_name='Biography')
    vision = models.CharField(max_length=1000, null=True, blank=True, verbose_name='Vision')
    spiritual_rebirth_day = models.DateField(auto_now=False, auto_now_add=False, null=True, blank=True, verbose_name='Spiritual Rebirth Days')
    academic_record = models.OneToOneField(AcademicRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name="member_academic_record")

    denomination_branch = models.CharField(
        max_length=40,
        choices=CHURCH_BRANCH_CHOICES,
        null=False, blank=False,
        verbose_name='Denomination Branch'
    )
    denomination_family = models.CharField(
        max_length=60,
        choices=CHURCH_FAMILY_CHOICES_ALL,
        null=True, blank=True,                     
        verbose_name='Denomination Family (Optional)'
    )
    
    show_gifts_in_profile = models.BooleanField(default=True, verbose_name=_("Show Gifts in Profile"), help_text=_("Allow gifts to be visible on the profile page."))
    show_fellowship_in_profile = models.BooleanField(default=True, verbose_name='Show Fellowship in Profile')
    hide_confidants = models.BooleanField(default=False, verbose_name='Hide Confidants in setting')
    
    testimonies = GenericRelation(
        Testimony,
        related_query_name='owner_member',
        content_type_field='content_type',
        object_id_field='object_id'
    )
    register_date = models.DateField(default=timezone.now, verbose_name='Register Date')

    identity_document = models.FileField(upload_to=FILE.dir_upload, null=True, blank=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='Identity Document')
    identity_verified_at = models.DateTimeField(null=True, blank=True, verbose_name='Identity Verified At')
    identity_verification_status = models.CharField(max_length=20, choices=IDENTITY_VERIFICATION_STATUS_CHOICES, default=NOT_SUBMITTED, verbose_name='Identity Verification Status')
    is_verified_identity = models.BooleanField(default=False, verbose_name="Verified Identity")
    is_sanctuary_participant = models.BooleanField(default=False, verbose_name="Sanctuary Participant")

    is_hidden_by_confidants = models.BooleanField(default=False, verbose_name='Hidden by Confidants')    
    is_privacy = models.BooleanField(default=False, verbose_name='Is Privacy')
    
    is_migrated = models.BooleanField(default=False, verbose_name='Is Migrated')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'member_detail' 

    def get_slug_source(self):
        return self.user.username
        
    def is_manager(self):
        return self.organization_adminships.exists()

    def managed_organizations(self):
        return self.organization_adminships.all()

    def clean(self):
        # Enforce: family (if provided) must belong to the selected branch
        branch = self.denomination_branch
        family = self.denomination_family
        if family:
            allowed = FAMILIES_BY_BRANCH.get(branch, set())
            if family not in allowed:
                raise ValidationError({
                    "denomination_family": "Selected family does not belong to the chosen branch."
                })
    
    class Meta:
        verbose_name = "1. Member"
        verbose_name_plural = "1. Members"

    def __str__(self):
        return self.user.username
    


# GUESTUSER Manager -------------------------------------------------------------------------------------------
class GuestUser(SlugMixin):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="guest_profile", verbose_name='User')
    register_date = models.DateField(default=timezone.now, verbose_name='Register Date')      
    is_migrated = models.BooleanField(default=False, verbose_name='Is Migrated')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'guest_user_detail' 


    def get_slug_source(self):
        return self.user.username
        
    class Meta:
        verbose_name = "2. Guest User"
        verbose_name_plural = "2. Guest Users"

    def __str__(self):
        return self.user.username


# CLIENT Manager -------------------------------------------------------------------------------------------- 
# Request
class ClientRequest(models.Model):
    DOCUMENT = FileUpload('profiles', 'documents', 'client_request')

    id = models.BigAutoField(primary_key=True)
    request = models.CharField(max_length=50, verbose_name='Request')
    description = models.CharField(max_length=500, verbose_name='Description')
    document_1 = models.FileField(upload_to=DOCUMENT.dir_upload, null=True, blank=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='Document 1')
    document_2 = models.FileField(upload_to=DOCUMENT.dir_upload, null=True, blank=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='Document 2')
    
    register_date = models.DateField(default=timezone.now, verbose_name='Register Date')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    
    class Meta:
        verbose_name = "Client Request"
        verbose_name_plural = "Client Requests"

    def __str__(self):
        return self.request
    
# Client Model
class Client(SlugMixin):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="client_profile", verbose_name='User')
    organization_clients = models.ManyToManyField('profilesOrg.Organization', blank=True, related_name='organization_clients', verbose_name='Organization Clients')
    request = models.ForeignKey(ClientRequest, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Request")
    register_date = models.DateField(default=timezone.now, verbose_name='Register Date')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'client_detail' 
    
    def get_slug_source(self):
        return self.name.username
        
    class Meta:
        verbose_name = "4. Client"
        verbose_name_plural = "4. Clients"

    def __str__(self):
        return self.name.username


# CUSTOMER Manager ------------------------------------------------------------------------------------------ 
class Customer(SlugMixin):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="customer_profile", verbose_name='User')
    billing_address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True, blank=True, related_name='customer_billing_addresses', verbose_name='Billing Address')
    shipping_addresses = models.ManyToManyField(Address, related_name='customer_shipping_addresses', verbose_name='Shipping Addresses')
    customer_phone_number = models.CharField(max_length=20, validators=[validate_phone_number], verbose_name='Phone Number')
    register_date = models.DateField(default=timezone.now, verbose_name='Register Date')
    deactivation_reason = models.CharField(max_length=50, choices=CUSTOMER_DEACTIVATION_REASON_CHOICES, null=True, blank=True, verbose_name='Deactivation Reason')
    deactivation_note = models.TextField(null=True, blank=True, verbose_name='Deactivation Note')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'customer_detail' 

    def get_slug_source(self):
        return self.name.username
    
    class Meta:
        verbose_name = "5. Customer"
        verbose_name_plural = "5. Customers"

        
    def __str__(self):
        shipping_address = self.shipping_addresses.first()
        return f"{self.name.username} - Shipping Address: {shipping_address if shipping_address else 'No shipping address'}"










# Sprituual Gifts List ---------------------------------------------------------------------------------
class SpiritualGift(models.Model):
    name = models.CharField(max_length=100, choices=GIFT_CHOICES, verbose_name=_("Spiritual Gift Name"))
    description = models.TextField(verbose_name=_("Description"))

    def save(self, *args, **kwargs):
        if not self.description:
            self.description = GIFT_DESCRIPTIONS.get(self.name, _('No description available'))
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = _("Spiritual Gift")
        verbose_name_plural = _("Spiritual Gifts")
    
    def __str__(self):
        return self.get_name_display()


# Sprituual Gifts Survey Question ----------------------------------------------------------------------
class SpiritualGiftSurveyQuestion(models.Model):
    question_text = models.CharField(max_length=500, verbose_name=_("Question Text"))
    question_number = models.IntegerField(verbose_name=_("Question Number"))
    language = models.CharField(max_length=10, choices=GIFT_LANGUAGE_CHOICES, verbose_name=_("Language"))
    options = models.JSONField(verbose_name=_("Options"))
    gift = models.ForeignKey(SpiritualGift, on_delete=models.CASCADE, verbose_name=_("Spiritual Gift"))
    
    class Meta:
        verbose_name = _("Spiritual Gift Survey Question")
        verbose_name_plural = _("Spiritual Gift Survey Questions")
    
    def __str__(self):
        return f"{self.question_text} ({self.language})"


# Sprituual Gifts Survey Response -----------------------------------------------------------------------
class SpiritualGiftSurveyResponse(models.Model):
    id = models.BigAutoField(primary_key=True)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name=_("Member"))
    question = models.ForeignKey(SpiritualGiftSurveyQuestion, on_delete=models.CASCADE, verbose_name=_("Question"))
    question_number = models.IntegerField(verbose_name=_("Question Number"))
    answer = models.IntegerField(choices=ANSWER_CHOICES, verbose_name=_("Answer"))
    
    class Meta:
        verbose_name = _("Spiritual Gift Survey Response")
        verbose_name_plural = _("Spiritual Gift Survey Responses")
    
    def __str__(self):
        return f"Response by {self.member} for question {self.question.id}"


# Member Survey Progress ---------------------------------------------------------------------------------
class MemberSurveyProgress(models.Model):
    id = models.BigAutoField(primary_key=True)
    member = models.OneToOneField(Member, on_delete=models.CASCADE, verbose_name=_("Member"))
    current_question = models.IntegerField(default=1, verbose_name=_("Current Question"))
    answered_questions = models.JSONField(default=list, verbose_name=_("Answered Questions"))
    incomplete_survey = models.BooleanField(default=False, verbose_name=_("Incomplete Survey"))
    
    class Meta:
        verbose_name = _("Member Survey Progress")
        verbose_name_plural = _("Member Survey Progresses")
    
    def __str__(self):
        return f"Survey progress for {self.member.username}"


# Member Sprituual Gifts ----------------------------------------------------------------------------------
class MemberSpiritualGifts(models.Model):
    id = models.BigAutoField(primary_key=True)
    member = models.OneToOneField(Member, on_delete=models.CASCADE, verbose_name=_("Member"))
    gifts = models.ManyToManyField(SpiritualGift, verbose_name=_("Spiritual Gifts"))
    survey_results = models.JSONField(verbose_name=_("Survey Results"))
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_("Created At"))
    
    class Meta:
        verbose_name = _("User Spiritual Gifts")
        verbose_name_plural = _("User Spiritual Gifts")

    def __str__(self):
        return f"Spiritual Gifts of {self.member}"

        
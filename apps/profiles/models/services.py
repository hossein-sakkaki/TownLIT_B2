# apps/profiles/models/services.py

from django.conf import settings
from django.db import models

from apps.profiles.constants.ministry import STANDARD_MINISTRY_CHOICES
from utils.common.utils import FileUpload
from validators.mediaValidators.pdf_validators import validate_pdf_file
from validators.security_validators import validate_no_executable_file


class SpiritualService(models.Model):
    name = models.CharField(
        max_length=40,
        choices=STANDARD_MINISTRY_CHOICES,
        unique=True,
        verbose_name="Name of Service",
    )
    description = models.CharField(
        max_length=300,
        null=True,
        blank=True,
        verbose_name="Description",
    )
    is_sensitive = models.BooleanField(default=False, verbose_name="Requires Credential")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")

    class Meta:
        verbose_name = "Spiritual Service"
        verbose_name_plural = "Spiritual Services"

    def __str__(self):
        return self.name


class MemberServiceType(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ACTIVE = "active", "Active (no approval needed)"

    DOCUMENT = FileUpload("profiles", "documents", "member_service_type")

    id = models.BigAutoField(primary_key=True)
    service = models.ForeignKey(
        SpiritualService,
        on_delete=models.CASCADE,
        related_name="service_instances",
    )
    history = models.CharField(max_length=500, null=True, blank=True)
    document = models.FileField(
        upload_to=DOCUMENT,
        blank=True,
        null=True,
        validators=[validate_pdf_file, validate_no_executable_file],
    )

    credential_issuer = models.CharField(max_length=120, null=True, blank=True)
    credential_number = models.CharField(max_length=80, null=True, blank=True)
    credential_url = models.URLField(null=True, blank=True)
    issued_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, db_index=True)
    review_note = models.CharField(max_length=300, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    register_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "MemberServiceType"
        verbose_name_plural = "MemberServiceTypes"

    def __str__(self):
        return self.service.name
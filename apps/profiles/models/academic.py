# apps/profiles/models/academic.py
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from apps.profiles.constants.education import (
    EDUCATION_DOCUMENT_TYPE_CHOICES,
    EDUCATION_DEGREE_CHOICES,
)
from utils.common.utils import FileUpload
from validators.mediaValidators.pdf_validators import validate_pdf_file
from validators.security_validators import validate_no_executable_file


class StudyStatus(models.TextChoices):
    IN_PROGRESS = "in_progress", _("In Progress")
    COMPLETED = "completed", _("Completed")
    ON_HOLD = "on_hold", _("On Hold")
    DROPPED = "dropped", _("Dropped")


class AcademicRecord(models.Model):
    DOCUMENT = FileUpload("profiles", "documents", "academic_record")

    id = models.BigAutoField(primary_key=True)
    education_document_type = models.CharField(
        max_length=50,
        choices=EDUCATION_DOCUMENT_TYPE_CHOICES,
        verbose_name="Education Document Type",
    )
    education_degree = models.CharField(
        max_length=100,
        choices=EDUCATION_DEGREE_CHOICES,
        verbose_name="Education Degree",
    )
    school = models.CharField(max_length=100, verbose_name="School")
    country = models.CharField(max_length=100, verbose_name="Country")

    started_at = models.DateField(
        null=True,
        blank=True,
        verbose_name="Started At (YYYY-MM-01)",
    )
    expected_graduation_at = models.DateField(
        null=True,
        blank=True,
        verbose_name="Expected Graduation (YYYY-MM-01)",
    )
    graduated_at = models.DateField(
        null=True,
        blank=True,
        verbose_name="Graduated At (YYYY-MM-01)",
    )
    status = models.CharField(
        max_length=20,
        choices=StudyStatus.choices,
        default=StudyStatus.IN_PROGRESS,
        verbose_name="Study Status",
    )
    document = models.FileField(
        upload_to=DOCUMENT,
        null=True,
        blank=True,
        validators=[validate_pdf_file, validate_no_executable_file],
        verbose_name="Document",
    )

    is_theology_related = models.BooleanField(default=False, verbose_name="Theology Related")
    is_approved = models.BooleanField(default=False, verbose_name="Is Approved")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")

    class Meta:
        verbose_name = "Academic Record"
        verbose_name_plural = "Academic Records"
        ordering = ["-started_at", "-graduated_at", "-expected_graduation_at", "-id"]

    def __str__(self):
        return f"{self.education_degree}"

    def get_absolute_url(self):
        return reverse("academic_record_detail", kwargs={"pk": self.pk})

    @staticmethod
    def _ensure_first_of_month(value):
        # Keep month-level precision.
        if value and value.day != 1:
            return value.replace(day=1)
        return value

    def clean(self):
        errors = {}

        self.started_at = self._ensure_first_of_month(self.started_at)
        self.expected_graduation_at = self._ensure_first_of_month(self.expected_graduation_at)
        self.graduated_at = self._ensure_first_of_month(self.graduated_at)

        if self.started_at and self.expected_graduation_at:
            if self.expected_graduation_at < self.started_at:
                errors["expected_graduation_at"] = _(
                    "Expected graduation cannot be before start date."
                )

        if self.started_at and self.graduated_at:
            if self.graduated_at < self.started_at:
                errors["graduated_at"] = _("Graduation date cannot be before start date.")

        if self.status == StudyStatus.COMPLETED:
            if not self.graduated_at:
                errors["graduated_at"] = _(
                    "Graduated date is required when status is 'Completed'."
                )
        elif self.status == StudyStatus.IN_PROGRESS:
            if self.graduated_at:
                errors["graduated_at"] = _(
                    "Remove graduation date for 'In Progress' status."
                )
        elif self.status == StudyStatus.DROPPED:
            if self.graduated_at:
                errors["graduated_at"] = _(
                    "Do not set graduation date when status is 'Dropped'."
                )

        if errors:
            raise ValidationError(errors)

    @property
    def period_display(self) -> str:
        # Human-friendly period for UI.
        def ym(value):
            return value.strftime("%Y %b") if value else "—"

        if self.status == StudyStatus.IN_PROGRESS:
            start = ym(self.started_at)
            exp = ym(self.expected_graduation_at) if self.expected_graduation_at else None
            tail = f" (expected {exp})" if exp else ""
            return f"{start} – present{tail}"

        if self.status == StudyStatus.COMPLETED and self.started_at and self.graduated_at:
            return f"{ym(self.started_at)} – {ym(self.graduated_at)}"

        if self.status == StudyStatus.DROPPED:
            return f"{ym(self.started_at)} – dropped"

        if self.status == StudyStatus.ON_HOLD:
            base = f"{ym(self.started_at)} – on hold"
            if self.expected_graduation_at:
                base += f" (expected {ym(self.expected_graduation_at)})"
            return base

        if self.graduated_at:
            return f"graduated {ym(self.graduated_at)}"
        if self.started_at:
            return f"since {ym(self.started_at)}"
        return "—"
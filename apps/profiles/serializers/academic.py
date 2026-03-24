# apps/profiles/serializers/academic.py

from rest_framework import serializers
from apps.profiles.models.academic import AcademicRecord


# ACADEMIC RECORD Serializer --------------------------------------------------------------------------------
class YearMonthDateField(serializers.DateField):
    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m", input_formats=["%Y-%m", "%Y-%m-%d"], **kwargs)

    def to_internal_value(self, value):
        date = super().to_internal_value(value)
        # force day=1 to keep month-level precision
        return date.replace(day=1)

class AcademicRecordSerializer(serializers.ModelSerializer):
    started_at = YearMonthDateField(required=False, allow_null=True)
    expected_graduation_at = YearMonthDateField(required=False, allow_null=True)
    graduated_at = YearMonthDateField(required=False, allow_null=True)
    period_display = serializers.ReadOnlyField()

    class Meta:
        model = AcademicRecord
        fields = [
            'id',
            'education_document_type', 'education_degree', 'school', 'country',
            'status',
            'started_at', 'expected_graduation_at', 'graduated_at',
            'document',
            'is_theology_related',
            'is_approved', 'is_active',
            'period_display',
        ]
        read_only_fields = ['document', 'period_display']




from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import SanctuaryRequest, SanctuaryReview, SanctuaryOutcome




# SANCTUARY REQUEST Serializer --------------------------------------------------------------------
class SanctuaryRequestSerializer(serializers.ModelSerializer):
    content_type = serializers.SlugRelatedField(queryset=ContentType.objects.all(), slug_field='model')
    content_object_id = serializers.IntegerField(source='object_id')

    class Meta:
        model = SanctuaryRequest
        fields = [
            'id', 'request_type', 'reason', 'description', 'status', 'request_date',
            'requester', 'assigned_admin', 'content_type', 'content_object_id'
        ]
        read_only_fields = ['request_date', 'status', 'requester', 'assigned_admin']


# SANCTUARY REVIEW Serializer --------------------------------------------------------------------
class SanctuaryReviewSerializer(serializers.ModelSerializer):
    sanctuary_request = serializers.PrimaryKeyRelatedField(queryset=SanctuaryRequest.objects.all())
    reviewer = serializers.ReadOnlyField(source='reviewer.username')

    class Meta:
        model = SanctuaryReview
        fields = ['id', 'sanctuary_request', 'reviewer', 'review_status', 'comment', 'review_date', 'assigned_at']
        read_only_fields = ['review_date', 'reviewer', 'assigned_at']


# SANCTUARY OUTCOME Serializer --------------------------------------------------------------------
class SanctuaryOutcomeSerializer(serializers.ModelSerializer):
    sanctuary_requests = serializers.PrimaryKeyRelatedField(many=True, queryset=SanctuaryRequest.objects.all())
    content_type = serializers.SlugRelatedField(queryset=ContentType.objects.all(), slug_field='model')
    content_object_id = serializers.IntegerField(source='object_id')
    appeal_message = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = SanctuaryOutcome
        fields = [
            'id', 'outcome_status', 'completion_date', 'sanctuary_requests',
            'content_type', 'content_object_id', 'is_appealed', 'admin_reviewed', 'appeal_message'
        ]
        read_only_fields = ['completion_date', 'is_appealed', 'admin_reviewed']

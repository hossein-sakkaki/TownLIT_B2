from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .models import SanctuaryRequest, SanctuaryOutcome, SanctuaryReview
from .serializers import SanctuaryRequestSerializer, SanctuaryOutcomeSerializer, SanctuaryReviewSerializer
from apps.sanctuary.constants import SENSITIVE_CATEGORIES
from common.permissions import IsSanctuaryVerifiedMember


from .signals.signals import (
                        update_reports_count, distribute_to_verified_members, notify_admins, check_vote_completion,
                        notify_admins_of_appeal, notify_requester_and_reported, notify_sanctuary_participants, finalize_sanctuary_outcome
                    )



# SANCTUARY REQUSE Viewset -----------------------------------------------------------------------------------------------------------
class SanctuaryRequestViewSet(viewsets.ModelViewSet):
    queryset = SanctuaryRequest.objects.all()
    serializer_class = SanctuaryRequestSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        request_obj = serializer.save(requester=self.request.user)
        is_suspended = update_reports_count(sender=SanctuaryRequest, instance=request_obj, created=True)
        if is_suspended:
            all_related_requests = SanctuaryRequest.objects.filter(
                content_type=request_obj.content_type, object_id=request_obj.object_id
            )
            has_sensitive_reason = any(req.reason in SENSITIVE_CATEGORIES.get(req.request_type, []) for req in all_related_requests)
            if has_sensitive_reason:
                notify_admins(request_obj)
            else:
                distribute_to_verified_members(request_obj)


# SANCTUARY REVIEW Viewset ------------------------------------------------------------------------------------------------------------
class SanctuaryReviewViewSet(viewsets.ModelViewSet):
    queryset = SanctuaryReview.objects.all()
    serializer_class = SanctuaryReviewSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        review = serializer.save(reviewer=self.request.user)
        check_vote_completion(review.sanctuary_request)


# SANCTUARY OUTCOME Viewset ------------------------------------------------------------------------------------------------------------
class SanctuaryOutcomeViewSet(viewsets.ModelViewSet):
    queryset = SanctuaryOutcome.objects.all()
    serializer_class = SanctuaryOutcomeSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        outcome_obj = serializer.save()
        outcome_obj.appeal_deadline = timezone.now() + timedelta(days=7)
        outcome_obj.save()
        
        notify_sanctuary_participants(outcome_obj)
        if outcome_obj.is_appealed:
            notify_admins_of_appeal(outcome_obj)
        else:
            finalize_sanctuary_outcome(outcome_obj)

    def perform_update(self, serializer):
        outcome_obj = serializer.save()        
        if outcome_obj.is_appealed and not outcome_obj.admin_reviewed: # Handle appeals
            notify_admins_of_appeal(outcome_obj)
            
    @action(detail=True, methods=['post'])
    def appeal(self, request, pk=None):
        outcome = self.get_object()
        if timezone.now() > outcome.appeal_deadline:
            return Response({"detail": "The appeal deadline has passed. You can no longer appeal this outcome."}, status=status.HTTP_400_BAD_REQUEST)
        if outcome.is_appealed:
            return Response({"detail": "This outcome has already been appealed."}, status=status.HTTP_400_BAD_REQUEST)
        appeal_message = request.data.get('appeal_message', '')
        outcome.appeal_message = appeal_message
        outcome.is_appealed = True
        outcome.save()
        notify_admins_of_appeal(outcome)        
        return Response({"detail": "Appeal has been submitted."}, status=status.HTTP_200_OK)
        

# ADMIN SANCTUARY REVIEW Viewset -----------------------------------------------------------------------------------------------------------
class AdminSanctuaryReviewViewSet(viewsets.ModelViewSet):
    queryset = SanctuaryOutcome.objects.filter(is_appealed=True, admin_reviewed=False)
    serializer_class = SanctuaryOutcomeSerializer
    permission_classes = [IsAdminUser]

    def perform_update(self, serializer):
        outcome_obj = serializer.save()
        notify_requester_and_reported(outcome_obj.sanctuary_requests.first(), outcome_obj.outcome_status)


# SANCTUARY HISTORY Viewset -----------------------------------------------------------------------------------------------------------------
class SanctuaryHistoryViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        member = request.user
        
        # Fetch requests where the user is the requester
        requests = SanctuaryRequest.objects.filter(requester=member)
        requests_serializer = SanctuaryRequestSerializer(requests, many=True)

        # Fetch reviews where the user is a reviewer
        reviews = SanctuaryReview.objects.filter(reviewer=member)
        reviews_serializer = SanctuaryReviewSerializer(reviews, many=True)

        # Combine the data into a response
        history = {
            'requests': requests_serializer.data,
            'reviews': reviews_serializer.data
        }
        return Response(history)
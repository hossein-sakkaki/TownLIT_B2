# apps/profiles/views/member_spiritual_gifts.py

from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.profiles.models.gifts import (
    SpiritualGift,
    SpiritualGiftSurveyResponse,
    MemberSpiritualGifts,
    MemberSurveyProgress,
    SpiritualGiftSurveyQuestion,
)
from apps.profiles.serializers.gifts import MemberSpiritualGiftsSerializer, SpiritualGiftSurveyQuestionSerializer, SpiritualGiftSurveyResponseSerializer
from apps.profiles.services.gifts_service import (
    calculate_spiritual_gifts_scores,
    calculate_top_4_gifts,
)


# MEMBER'S SPIRITUAL GIFT Viewset  ---------------------------------------------------------------------------------
class MemberSpiritualGiftsViewSet(viewsets.ModelViewSet):
    queryset = MemberSpiritualGifts.objects.all()
    serializer_class = MemberSpiritualGiftsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        member = self.request.user.member_profile
        return MemberSpiritualGifts.objects.filter(member=member) 

    @action(detail=False, methods=['get'], url_path='spiritual-gifts', permission_classes=[IsAuthenticated])
    def get_spiritual_gifts_for_member(self, request):
        member = request.user.member_profile
        msg = "You haven't completed the Spiritual Gifts Discovery program yet. Click the button below to get started!"
        obj = MemberSpiritualGifts.objects.filter(member=member).first()
        if not obj:
            return Response(
                {"gifts": [], "created_at": None, "message": msg},
                status=status.HTTP_200_OK  
            )
        serializer = self.get_serializer(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='submit-survey', permission_classes=[IsAuthenticated])
    def submit_survey(self, request):
        member = request.user.member_profile
        last_submission = MemberSpiritualGifts.objects.filter(member=member).first()
        
        if last_submission and last_submission.created_at >= timezone.now() - timedelta(days=90):
            return Response({"error": "You can only participate in this course once every 90 days."}, status=status.HTTP_403_FORBIDDEN)

        survey_responses = SpiritualGiftSurveyResponse.objects.filter(member=member)        
        if not survey_responses.exists():
            return Response({"error": "No survey responses found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                member_spiritual_gifts, created = MemberSpiritualGifts.objects.get_or_create(
                    member=member,
                    defaults={"survey_results": {}},
                )
                if not created:
                    member_spiritual_gifts.created_at = timezone.now()

                scores = calculate_spiritual_gifts_scores(member)
                member_spiritual_gifts.survey_results = scores
                member_spiritual_gifts.save()

                top_4_gifts = calculate_top_4_gifts(scores)  # was: calculate_top_3_gifts
                member_spiritual_gifts.gifts.clear()

                # unchanged unpacking pattern (handles list when boundary tie happens)
                for gift_name in top_4_gifts:
                    if isinstance(gift_name, list):
                        for sub_gift in gift_name:
                            gift = SpiritualGift.objects.get(name=sub_gift)
                            member_spiritual_gifts.gifts.add(gift)
                    else:
                        gift = SpiritualGift.objects.get(name=gift_name)
                        member_spiritual_gifts.gifts.add(gift)

                # Delete all survay response
                survey_responses.delete()
                MemberSurveyProgress.objects.filter(member=member).delete()
                
            return Response({"message": "Survey completed successfully. You can retake it once every 90 days."}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# MEMBER'S GIFT QUESTIONS Viewset ------------------------------------------------------------------------------------    
class SpiritualGiftSurveyQuestionViewSet(viewsets.ModelViewSet):
    queryset = SpiritualGiftSurveyQuestion.objects.all()
    serializer_class = SpiritualGiftSurveyQuestionSerializer
    permission_classes = [IsAuthenticated]

    # Get all questions for the member in one request
    @action(detail=False, methods=['get'], url_path='gift-questions', permission_classes=[IsAuthenticated])
    def get_gift_questions(self, request):
        language = request.query_params.get('language', 'en')
        questions = self.get_queryset().filter(language=language)        
        serializer = self.get_serializer(questions, many=True)
        return Response(serializer.data)


# SPIRITUAL GIFT SURVEY Viewset ------------------------------------------------------------------------------------    
class SpiritualGiftSurveyViewSet(viewsets.ModelViewSet):
    queryset = SpiritualGiftSurveyResponse.objects.all()
    serializer_class = SpiritualGiftSurveyResponseSerializer
    permission_classes = [IsAuthenticated]
    
    # Get all responses for the current member
    @action(detail=False, methods=['get'], url_path='get-answers', permission_classes=[IsAuthenticated])
    def get_answers(self, request):
        user = request.user.member_profile
        responses = SpiritualGiftSurveyResponse.objects.filter(member=user)
        
        serializer = self.get_serializer(responses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='submit-answer', permission_classes=[IsAuthenticated])
    def submit_answer(self, request, pk=None):
        member = request.user.member_profile
        question_id = request.data.get('question_id')
        question_number = request.data.get('question_number')
        answer = request.data.get('answer')

        if question_number is None or answer is None:
            return Response({'error': 'Question ID and answer are required.'}, status=status.HTTP_400_BAD_REQUEST)

        question = get_object_or_404(SpiritualGiftSurveyQuestion, id=question_id, question_number=question_number)        
        existing_response = SpiritualGiftSurveyResponse.objects.filter(member=member, question_number=question_number).first()
        if existing_response:
            existing_response.answer = answer
            existing_response.save()
            message = 'Answer updated successfully.'
        else:
            SpiritualGiftSurveyResponse.objects.create(member=member, question=question, question_number=question_number, answer=answer)
            message = 'Answer submitted successfully.'

        progress, created = MemberSurveyProgress.objects.get_or_create(member=member)
        if question_number not in progress.answered_questions:
            progress.answered_questions.append(question_number)
        
        progress.current_question = max(progress.answered_questions)
        progress.save()

        return Response({'message': message}, status=status.HTTP_200_OK)
        
    @action(detail=False, methods=['get'], url_path='get-progress', permission_classes=[IsAuthenticated])
    def get_survey_progress(self, request):
        member = request.user.member_profile

        progress = MemberSurveyProgress.objects.filter(member=member).first()
        total_questions = (
            SpiritualGiftSurveyQuestion.objects
            .values('question_number')
            .distinct()
            .count()
        )

        # --------------------------------------------------
        # Case 1: Survey already started (incomplete)
        # --------------------------------------------------
        if progress:
            # Safety clamp (prevents invalid state)
            if progress.current_question > total_questions:
                progress.current_question = total_questions
                progress.save(update_fields=["current_question"])

            return Response(
                {
                    "current_question": progress.current_question,
                    "answered_questions": progress.answered_questions or [],
                    "completed": False,
                },
                status=status.HTTP_200_OK
            )

        # --------------------------------------------------
        # Case 2: Survey not started yet
        # --------------------------------------------------
        return Response(
            {
                "current_question": 0,
                "answered_questions": [],
                "completed": False,
            },
            status=status.HTTP_200_OK
        )

        
    @action(detail=False, methods=['delete'], url_path='cancel-survey', permission_classes=[IsAuthenticated])
    def cancel_survey(self, request):
        member = request.user.member_profile 
        SpiritualGiftSurveyResponse.objects.filter(member=member).delete()        
        MemberSurveyProgress.objects.filter(member=member).delete()
        return Response(
            {'message': 'Survey responses and progress have been reset successfully.'},
            status=status.HTTP_200_OK
        )
# apps/profiles/serializers/gifts.py

from rest_framework import serializers

from apps.profiles.models.gifts import (
    SpiritualGift,
    SpiritualGiftSurveyQuestion,
    SpiritualGiftSurveyResponse,
    MemberSpiritualGifts,
)
from apps.profiles.models.member import Member


class SpiritualGiftSerializer(serializers.ModelSerializer):
    name_display = serializers.CharField(source='get_name_display', read_only=True)

    class Meta:
        model = SpiritualGift
        fields = ['id', 'name', 'name_display', 'description']
        

# Gift Question serializer
class SpiritualGiftSurveyQuestionSerializer(serializers.ModelSerializer):
    gift = SpiritualGiftSerializer()

    class Meta:
        model = SpiritualGiftSurveyQuestion
        fields = ['id', 'question_text', 'question_number', 'language', 'options', 'gift']
        
# Gift Survey serializer
class SpiritualGiftSurveyResponseSerializer(serializers.ModelSerializer):
    question = SpiritualGiftSurveyQuestionSerializer()

    class Meta:
        model = SpiritualGiftSurveyResponse
        fields = ['id', 'member', 'question', 'answer']
        
    def validate_answer(self, value):
        if value < 1 or value > 7:
            raise serializers.ValidationError("Answer must be between 1 and 7.")
        return value

    def validate(self, data):
        question = data.get('question')
        member = data.get('member')
        if not SpiritualGiftSurveyQuestion.objects.filter(id=question.id).exists():
            raise serializers.ValidationError("The question is not valid.")
        if not Member.objects.filter(user=member).exists():
            raise serializers.ValidationError("The member is not valid.")
        return data
        
# Member Gifts serializer
class MemberSpiritualGiftsSerializer(serializers.ModelSerializer):
    gifts = SpiritualGiftSerializer(many=True)
    survey_results = serializers.JSONField()

    class Meta:
        model = MemberSpiritualGifts
        fields = ['member', 'gifts', 'survey_results', 'created_at']
        
        
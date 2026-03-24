# apps/profiles/admin/gifts.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.profiles.models.gifts import (
    SpiritualGift,
    SpiritualGiftSurveyQuestion,
    SpiritualGiftSurveyResponse,
    MemberSpiritualGifts,
)


@admin.register(SpiritualGift)
class SpiritualGiftAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    list_filter = ('name',)
    ordering = ('name',)


@admin.register(SpiritualGiftSurveyQuestion)
class SpiritualGiftSurveyQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'question_number', 'language', 'gift')
    search_fields = ('question_text', 'question_number', 'language')
    list_filter = ('language', 'gift')
    ordering = ('gift',)


@admin.register(SpiritualGiftSurveyResponse)
class SpiritualGiftSurveyResponseAdmin(admin.ModelAdmin):
    list_display = ('member', 'question', 'answer')
    search_fields = ('member_profile__user__username', 'question__question_text')
    list_filter = ('question',)
    ordering = ('member',)


@admin.register(MemberSpiritualGifts)
class MemberSpiritualGiftsAdmin(admin.ModelAdmin):
    list_display = ('member', 'get_gifts', 'survey_results')
    search_fields = ('member_profile__user__username',)
    list_filter = ('member',)
    ordering = ('member',)

    def get_gifts(self, obj):
        return ", ".join([gift.name for gift in obj.gifts.all()])
    get_gifts.short_description = _('Spiritual Gifts')
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.conf import settings

from .models import (
    EmailTemplate, EmailCampaign, EmailLog, 
    ScheduledEmail, UnsubscribedUser, DraftCampaign
)
from .forms import EmailCampaignAdminForm, EmailTemplateAdminForm


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    form = EmailTemplateAdminForm
    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
    list_display = ['name', 'subject_template', 'created_at', 'preview_link']
    search_fields = ['name', 'subject_template']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    fieldsets = (
        (None, {
            'fields': ('name', 'subject_template', 'body_template')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def preview_link(self, obj):
        url = reverse('communication:email-template-preview', args=[obj.pk])
        return format_html('<a href="{}" target="_blank">Preview</a>', url)
    preview_link.short_description = "Preview"

@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    form = EmailCampaignAdminForm
    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        
    list_display = ['title', 'status', 'target_group', 'scheduled_time', 'sent_at', 'created_by', 'preview_link', 'ignore_unsubscribe']
    list_filter = ['status', 'target_group', 'created_by']
    search_fields = ['title', 'subject']
    readonly_fields = ['sent_at', 'created_at']
    filter_horizontal = ['recipients']
    actions = ['send_campaign_now']


    def send_campaign_now(self, request, queryset):
        from .services import send_campaign_email_batch  # We'll implement this
        count = 0
        for campaign in queryset:
            if campaign.status == 'draft':
                send_campaign_email_batch(campaign.id)
                campaign.status = 'sent'
                campaign.save()
                count += 1
        self.message_user(request, f"{count} campaign(s) sent.")
    send_campaign_now.short_description = "Send selected campaigns now (manual)"
    
    def preview_link(self, obj):
        url = reverse('communication:email-campaign-preview', args=[obj.pk])
        return format_html('<a href="{}" target="_blank">Preview</a>', url)
    preview_link.short_description = "Preview"


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'user', 'email', 'sent_at', 'opened', 'clicked']
    list_filter = ['campaign', 'opened', 'clicked']
    search_fields = ['email']


@admin.register(ScheduledEmail)
class ScheduledEmailAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'run_at', 'is_sent']
    list_filter = ['is_sent']
    readonly_fields = ['created_at']


@admin.register(UnsubscribedUser)
class UnsubscribedUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'unsubscribed_at']
    search_fields = ['user__email']


@admin.register(DraftCampaign)
class DraftCampaignAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'last_edited']
    search_fields = ['campaign__title']
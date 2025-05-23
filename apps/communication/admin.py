from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.conf import settings
from django.utils.timezone import now
from datetime import timedelta
from django.contrib import messages

from .models import (
    EmailTemplate, EmailCampaign, EmailLog, 
    ScheduledEmail, UnsubscribedUser, DraftCampaign,
    ExternalEmailCampaign, ExternalContact
)
from .services import send_campaign_email_batch, send_external_email_campaign
from .forms import EmailCampaignAdminForm, EmailTemplateAdminForm


# EMAIL TEMPLATE Admin ----------------------------------------------------------------
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
            'fields': ('name', 'subject_template', 'body_template', 'layout')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    exclude = ['created_by']
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def preview_link(self, obj):
        url = reverse('communication:email-template-preview', args=[obj.pk])
        return format_html('<a href="{}" target="_blank">Preview</a>', url)
    preview_link.short_description = "Preview"


# EMAIL CAMPAIGN Admin ----------------------------------------------------------------
@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    form = EmailCampaignAdminForm
    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        
    list_display = [
            'title', 'status', 'target_group', 'scheduled_time', 'sent_at', 'created_by',
            'preview_link', 'ignore_unsubscribe', 
            'draft_note', 'edit_draft_link',
            'open_rate', 'click_rate'
        ]
    list_filter = ['status', 'target_group', 'created_by']
    search_fields = ['title', 'subject']
    readonly_fields = ['sent_at', 'created_at']
    filter_horizontal = ['recipients']
    actions = ['send_campaign_now']
    exclude = ['created_by']
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


    def send_campaign_now(self, request, queryset):
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
    
    def draft_note(self, obj):
        return obj.draft.notes if hasattr(obj, 'draft') else '-'
    draft_note.short_description = "Draft Notes"

    def edit_draft_link(self, obj):
        if hasattr(obj, 'draft'):
            url = reverse('admin:communication_draftcampaign_change', args=[obj.draft.id])
            return format_html('<a href="{}">Edit Draft</a>', url)
        return "-"
    edit_draft_link.short_description = "Draft"

    def open_rate(self, obj):
        total = obj.email_logs.count()
        opened = obj.email_logs.filter(opened=True).count()
        if total == 0:
            return "—"
        return f"{(opened / total) * 100:.1f}%"
    open_rate.short_description = "📬 Open Rate"

    def click_rate(self, obj):
        total = obj.email_logs.count()
        clicked = obj.email_logs.filter(clicked=True).count()
        if total == 0:
            return "—"
        return f"{(clicked / total) * 100:.1f}%"
    click_rate.short_description = "🔗 Click Rate"


# SCHEDULE EMAIL Admin ----------------------------------------------------------------
@admin.register(ScheduledEmail)
class ScheduledEmailAdmin(admin.ModelAdmin):
    list_display = ['campaign_title', 'run_at', 'is_sent', 'executed_at', 'time_until_send', 'created_at']
    list_filter = ['is_sent']
    readonly_fields = ['created_at', 'executed_at']
    ordering = ['-run_at']
    exclude = ['created_by']
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def campaign_title(self, obj):
        return obj.campaign.title
    campaign_title.short_description = "Campaign"

    def time_until_send(self, obj):
        if obj.is_sent:
            return "✅ Sent"
        now_time = now()
        if obj.run_at > now_time:
            delta: timedelta = obj.run_at - now_time
            minutes = int(delta.total_seconds() // 60)
            seconds = int(delta.total_seconds() % 60)
            return f"In {minutes}m {seconds}s"
        else:
            return "⌛ Awaiting Celery execution..."
    time_until_send.short_description = "⏱ Time Until Send"
    
    def resend_scheduled_email(self, request, queryset):
        count = 0
        for obj in queryset:
            if obj.is_sent:
                continue  # ❌ Already sent — skip it

            try:
                send_campaign_email_batch(obj.campaign.id)
                obj.is_sent = True
                obj.executed_at = now()
                obj.save()
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"❌ Failed to resend {obj.campaign.title}: {e}",
                    level=messages.ERROR
                )
        if count:
            self.message_user(request, f"✅ {count} scheduled email(s) resent successfully.")
        else:
            self.message_user(request, "ℹ️ No eligible scheduled emails were resent.", level=messages.INFO)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        server_time = now().strftime("%Y-%m-%d %H:%M:%S %Z")
        context['adminform'].form.fields['run_at'].help_text = format_html(
            '<div style="margin-top:8px;"><strong>🕒 Server Time (UTC):</strong> <code>{}</code></div>'
            '<div style="margin-top:4px; color:#999;">Use this to adjust your scheduled time.</div>', server_time
        )
        return super().render_change_form(request, context, add, change, form_url, obj)


# DRAFT CAMPAIGN Admin ----------------------------------------------------------------
@admin.register(DraftCampaign)
class DraftCampaignAdmin(admin.ModelAdmin):
    list_display = ['campaign_title', 'short_note', 'last_edited', 'convert_to_campaign_link']
    search_fields = ['campaign__title', 'notes']
    readonly_fields = ['last_edited']
    actions = ['convert_to_campaign_action']

    def campaign_title(self, obj):
        return obj.campaign.title
    campaign_title.short_description = "Campaign"

    def short_note(self, obj):
        return (obj.notes[:70] + "...") if obj.notes and len(obj.notes) > 70 else obj.notes
    short_note.short_description = "Notes"

    def convert_to_campaign_action(self, request, queryset):
        count = 0
        for draft in queryset:
            campaign = draft.campaign
            if draft.notes:
                # Insert logic: for now we put it in custom_html
                campaign.custom_html = draft.notes
                campaign.save()
                count += 1
        self.message_user(request, f"{count} draft(s) copied into campaign(s).")
    convert_to_campaign_action.short_description = "Convert draft notes to campaign content"

    def convert_to_campaign_link(self, obj):
        url = reverse('admin:communication_emailcampaign_change', args=[obj.campaign.id])
        return format_html('<a href="{}" class="button">Open Campaign</a>', url)
    convert_to_campaign_link.short_description = "Open Campaign"


@admin.register(UnsubscribedUser)
class UnsubscribedUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'unsubscribed_at']
    search_fields = ['user__email']
    list_filter = ['unsubscribed_at']
    readonly_fields = ['unsubscribed_at']
    

# EMAIL LOG Admin ----------------------------------------------------------------------
@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ['campaign_link', 'user', 'email', 'sent_at', 'opened', 'clicked']

    list_filter = ['campaign', 'opened', 'clicked']
    search_fields = ['email']
    list_filter += ['sent_at']
    search_fields = ['email', 'user__username']
    
    def campaign_link(self, obj):
        url = reverse('admin:communication_emailcampaign_change', args=[obj.campaign.id])
        return format_html('<a href="{}">{}</a>', url, obj.campaign.title)
    campaign_link.short_description = "Campaign"


# EXTERNAL EMAIL CAMPAIGN Admin -------------------------------------------------------
@admin.register(ExternalEmailCampaign)
class ExternalEmailCampaignAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        
    list_display = ['title', 'created_by', 'created_at', 'is_sent', 'sent_at', 'preview_link']
    readonly_fields = ['created_at', 'sent_at', 'is_sent']
    actions = ['send_external_campaign']
    exclude = ['created_by']
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        
    def preview_link(self, obj):
        url = reverse('communication:external-campaign-preview', args=[obj.pk])
        return format_html('<a href="{}" target="_blank">🔍 Preview</a>', url)
    preview_link.short_description = "Preview"

    def send_external_campaign(self, request, queryset):
        count = 0
        summary = []
        for campaign in queryset:
            if campaign.is_sent:
                continue
            try:
                result = send_external_email_campaign(campaign)
                count += 1
                summary.append(
                    f"<strong>{campaign.title}</strong>: "
                    f"✅ Sent: <b>{result['sent']}</b>, "
                    f"⚠️ Skipped: <b>{result['skipped_duplicates']}</b>, "
                    f"❌ Failed Saves: <b>{result['failed_saves']}</b>"
                )
            except Exception as e:
                self.message_user(request, f"❌ Failed to send {campaign.title}: {e}", level=messages.ERROR)

        if summary:
            self.message_user(
                request,
                format_html("<br>".join(summary)),
                level=messages.INFO
            )


# EXTERNAL CONTACT Admin ------------------------------------------------------------
@admin.register(ExternalContact)
class ExternalContactAdmin(admin.ModelAdmin):
    list_display = [
        'email', 'name', 'family', 'nation', 'country', 'phone',
        'source_campaign', 'is_unsubscribed', 'became_user', 'deleted_after_signup', 'created_at'
    ]
    search_fields = ['email', 'name', 'family', 'phone']
    list_filter = [
        'nation', 'country', 'gender', 'source_campaign',
        'is_unsubscribed', 'became_user', 'deleted_after_signup'
    ]
    readonly_fields = ['created_at']
    ordering = ['-created_at']

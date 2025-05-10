# communication/services.py

from django.conf import settings
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from django.template import Template, Context

from .models import EmailCampaign, EmailLog, UnsubscribedUser
from utils.email.email_tools import send_custom_email
from utils.email.token_generator import generate_unsubscribe_token
from utils.email.template_context import validate_template_variables

CustomUser = get_user_model()


def send_campaign_email_batch(campaign_id):
    # Validate body content before sending
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
    except EmailCampaign.DoesNotExist:
        print("❌ Campaign not found.")
        return

    if campaign.status == 'sent':
        print("⏩ Already sent.")
        return
    
    # --- Validate template content ---
    body_source = campaign.custom_html or (campaign.template.body_template if campaign.template else '')
    try:
        validate_template_variables(body_source)
    except ValueError as e:
        print(f"❌ Email not sent. Reason: {e}")
        return

    # --- Select target users ---
    if campaign.recipients.exists():
        # Personal message: send to recipients regardless of unsubscribe
        users = campaign.recipients.filter(is_active=True)

    else:
        # Group message: apply unsubscribe logic based on campaign settings
        users = CustomUser.objects.filter(is_active=True)

        if campaign.target_group == 'active':
            users = users.filter(last_login__isnull=False)
        elif campaign.target_group == 'members':
            users = users.filter(member__isnull=False)

        # Exclude unsubscribed users if not forced
        if not campaign.ignore_unsubscribe:
            unsubscribed_user_ids = UnsubscribedUser.objects.values_list('user_id', flat=True)
            users = users.exclude(id__in=unsubscribed_user_ids)

    # --- Send emails ---
    sent_count = 0
    for user in users:
        email = user.email
        token = generate_unsubscribe_token(user.id)

        context = {
            'email': email,
            'first_name': user.name,
            'username': user.username,
            'site_domain': settings.SITE_URL,
            'unsubscribe_url': f"{settings.SITE_URL}/communication/unsubscribe/{token}/",
        }

        # Render email content
        raw_template = campaign.custom_html or (campaign.template.body_template if campaign.template else '')
        template = Template(raw_template)
        context['content'] = template.render(Context(context))
        
        # Render subject
        subject_raw = campaign.subject or (campaign.template.subject_template if campaign.template else '')
        subject_template = Template(subject_raw)
        rendered_subject = subject_template.render(Context(context))

        success = send_custom_email(
            to=email,
            subject=rendered_subject,
            template_path='emails/newsletter/base_newsletter.html',
            context=context
        )

        if success:
            EmailLog.objects.create(
                campaign=campaign,
                user=user,
                email=email
            )
            sent_count += 1

    # --- Finalize ---
    campaign.status = 'sent'
    campaign.sent_at = now()
    campaign.save()

    print(f"✅ Sent {sent_count} emails.")


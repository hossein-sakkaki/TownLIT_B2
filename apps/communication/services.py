import csv, json, io
from django.conf import settings
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from django.template import Template, Context
from datetime import datetime
from django.utils import timezone


from .models import EmailCampaign, EmailLog, UnsubscribedUser, ExternalContact
from utils.email.email_tools import send_custom_email
from utils.email.token_generator import generate_email_opt_token, generate_external_email_token
from utils.email.template_context import validate_template_variables
from utils.common.file_reader import read_csv_or_json

CustomUser = get_user_model()


# Filters For Campaign --------------------------------------------------------------------
def get_users_for_campaign(campaign):
    tg = campaign.target_group
    users = CustomUser.objects.all()

    if campaign.recipients.exists():
        # Personal messages — ignore target group and unsubscribe logic
        return campaign.recipients.filter(is_active=True)

    if tg == 'all_active':
        users = users.filter(is_active=True)

    elif tg == 'believer':
        users = users.filter(is_active=True, label__name='believer')

    elif tg == 'seeker':
        users = users.filter(is_active=True, label__name='seeker')

    elif tg == 'prefer_not_to_say':
        users = users.filter(is_active=True, label__name='prefer_not_to_say')

    elif tg == 'seeker_and_prefer_not_to_say':
        users = users.filter(is_active=True, label__name__in=['seeker', 'prefer_not_to_say'])

    elif tg == 'admins':
        users = users.filter(is_active=True, is_admin=True)

    elif tg == 'deleted_members':
        users = users.filter(is_active=False, member__isnull=False)

    elif tg == 'deleted_non_members':
        users = users.filter(is_active=False, member__isnull=True)

    elif tg == 'suspended':
        users = users.filter(is_active=True, is_suspended=True)

    elif tg == 'sanctuary_participants':
        users = users.filter(
            is_active=True,
            member__isnull=False,
            member__is_sanctuary_participant=True
        )

    elif tg == 'privacy_enabled':
        users = users.filter(
            is_active=True,
            member__isnull=False,
            member__is_privacy=True
        )

    elif tg == 'unverified_identity':
        users = users.filter(
            is_active=True,
            member__isnull=False,
            member__is_verified_identity=False
        )
    
    elif tg == 'reengagement':
        unsub_ids = UnsubscribedUser.objects.values_list('user_id', flat=True)
        users = CustomUser.objects.filter(id__in=unsub_ids, is_active=True)

    else:
        # fallback → all active
        users = users.filter(is_active=True)

    # Filter out unsubscribed users unless this is a forced or reengagement campaign
    if not campaign.ignore_unsubscribe and campaign.target_group != 'reengagement':
        unsubscribed_user_ids = UnsubscribedUser.objects.values_list('user_id', flat=True)
        users = users.exclude(id__in=unsubscribed_user_ids)

    return users




# Send Campaign Email Engin --------------------------------------------------------------------
def send_campaign_email_batch(campaign_id):
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
    except EmailCampaign.DoesNotExist:
        print("❌ Campaign not found.")
        return

    if campaign.status == 'sent':
        print("⏩ Already sent.")
        return

    # --- Validate email template variables ---
    body_source = campaign.custom_html or (campaign.template.body_template if campaign.template else '')
    try:
        validate_template_variables(body_source)
    except ValueError as e:
        print(f"❌ Email not sent. Reason: {e}")
        return

    # --- Select target users (delegated to helper) ---
    users = get_users_for_campaign(campaign)

    # --- Send emails ---
    sent_count = 0
    for user in users:
        email = user.email
        token = generate_email_opt_token(user.id)

        context = {
            'email': email,
            'user': user,
            'first_name': user.name,
            'username': user.username,
            'site_domain': settings.SITE_URL,
            "logo_base_url": settings.EMAIL_LOGO_URL,
            "current_year": timezone.now().year,
            'unsubscribe_url': f"{settings.SITE_URL}/communication/unsubscribe/{token}/",
        }
        
        # ✅ Add resubscribe link only for reengagement campaigns
        if campaign.target_group == 'reengagement':
            context['resubscribe_url'] = f"{settings.SITE_URL}/communication/resubscribe/{token}/"

        # Render email content
        raw_template = campaign.custom_html or (campaign.template.body_template if campaign.template else '')
        template = Template(raw_template)
        context['content'] = template.render(Context(context))

        # Render subject
        subject_raw = campaign.subject or (campaign.template.subject_template if campaign.template else '')
        subject_template = Template(subject_raw)
        rendered_subject = subject_template.render(Context(context))
        

        if campaign.template and hasattr(campaign.template, 'layout'):
            layout = campaign.template.layout  # مقدار مثل 'base_site' یا 'base_email'
        else:
            layout = 'base_site'  # مقدار پیش‌فرض

        template_path = f'{layout}.html'

        success = send_custom_email(
            to=email,
            subject=rendered_subject,
            template_path=template_path,
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



# Send External Campaign Email Engin --------------------------------------------------------------------
def send_external_email_campaign(campaign):
    rows = []

    try:
        with campaign.csv_file.open('rb') as f:
            rows = read_csv_or_json(f)
    except Exception as e:
        raise Exception(f"Failed to read CSV or JSON file: {e}")

    if not rows:
        print("⚠️ No valid data found in the uploaded file.")
        return 0
    
    # Fetch all CustomUser Registred
    registered_emails = set(
        CustomUser.objects.values_list('email', flat=True)
    )
    registered_emails = {email.strip().lower() for email in registered_emails}

    # Fetch all previously saved emails (lowercased)
    existing_emails = set(
        ExternalContact.objects.values_list('email', flat=True)
    )
    existing_emails = {email.strip().lower() for email in existing_emails}

    unique_emails = set()
    sent_count = 0
    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for row in rows:
        email = row.get("email", "").strip().lower()
        if not email or email in unique_emails or email in existing_emails or email in registered_emails:
            skipped_count += 1
            continue
        unique_emails.add(email)

        def parse_date(date_str, fmt):
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except:
                return None

        birth_date = parse_date(row.get("birth_date", ""), "%Y-%m-%d")
        registre_date = parse_date(row.get("registre_date", ""), "%Y-%m-%d %H:%M:%S.%f") or \
                        parse_date(row.get("registre_date", ""), "%Y-%m-%d %H:%M:%S")

        # Save new contact
        try:
            ExternalContact.objects.create(
                email=email,
                name=row.get("name", "").strip(),
                family=row.get("family", "").strip(),
                gender=row.get("gender", "").strip(),
                birth_date=birth_date,
                nation=row.get("nation", "").strip(),
                country=row.get("country", "").strip(),
                phone=row.get("phone", "").strip(),
                recognize=row.get("recognize", "").strip(),
                registre_date=registre_date,
                source_campaign=campaign,
            )
        except Exception as e:
            print(f"⚠️ Failed to save external contact {email}: {e}")
            failed_count += 1
            continue  # Skip sending email if saving fails
                
        unsubscribe_token = generate_external_email_token(email)
        unsubscribe_url = f"{settings.SITE_URL}/communication/external-unsubscribe/{unsubscribe_token}/"
        context = {
            'email': email,
            'first_name': row.get("name", "Friend"),
            'username': row.get("name", "guest_user"),
            'site_domain': settings.SITE_URL,
            "logo_base_url": settings.EMAIL_LOGO_URL,
            "current_year": timezone.now().year,
            'unsubscribe_url': unsubscribe_url,
        }

        try:
            body_template = Template(campaign.html_body)
            subject_template = Template(campaign.subject)

            context['content'] = body_template.render(Context(context))
            rendered_subject = subject_template.render(Context(context))
            
            # Skip if unsubscribed or already registered
            if ExternalContact.objects.filter(email=email, is_unsubscribed=True) \
                | ExternalContact.objects.filter(email=email, became_user=True):
                continue
            
            template_path = 'base_site.html'

            success = send_custom_email(
                to=email,
                subject=rendered_subject,
                template_path=template_path,
                context=context
            )

            if success:
                sent_count += 1
            else:
                print(f"❌ Email not sent to {email}: send_custom_email returned False")

        except Exception as e:
            print(f"❌ Failed to send to {email}: {e}")

    campaign.is_sent = True
    campaign.sent_at = now()
    campaign.save()

    print(f"✅ Sent {sent_count} emails successfully.")
    
    return {
        "sent": sent_count,
        "skipped_duplicates": skipped_count,
        "failed_saves": failed_count,
    }

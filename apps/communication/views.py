from rest_framework.views import APIView
from django.views import View
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.template import Template, Context

from .models import UnsubscribedUser, EmailTemplate, ExternalEmailCampaign, EmailCampaign
from utils.email.token_generator import validate_email_opt_token, validate_external_email_token
from django.contrib.auth import get_user_model
from utils.common.file_reader import read_csv_or_json
from .models import ExternalEmailCampaign

CustomUser = get_user_model()


# Email Template Preview View --------------------------------------------------------
class EmailTemplatePreviewView(View):
    def get(self, request, pk):
        template = get_object_or_404(EmailTemplate, pk=pk)
        context = {
            'subject': template.subject_template,
            'content': template.body_template,
            'site_domain': settings.SITE_URL,
            'unsubscribe_url': '#'
        }
        return render(request, 'emails/newsletter/base_newsletter.html', context)
    

# Email Campaign Preview View --------------------------------------------------------
class EmailCampaignPreviewView(APIView):
    def get(self, request, pk):
        campaign = get_object_or_404(EmailCampaign, pk=pk)

        content = campaign.custom_html or (campaign.template.body_template if campaign.template else "")
        context = {
            "subject": campaign.subject,
            "content": content,
            "site_domain": settings.SITE_URL,
            "unsubscribe_url": "#"
        }

        return render(request, "emails/newsletter/base_newsletter.html", context)
    

# External Email Campaign Preview View ------------------------------------------------
class ExternalCampaignPreviewView(View):
    def get(self, request, pk):
        campaign = get_object_or_404(ExternalEmailCampaign, pk=pk)

        try:
            with campaign.csv_file.open('rb') as f:
                rows = read_csv_or_json(f)
            if not rows:
                raise ValueError("No data found in uploaded file.")
            first_row = rows[0]
        except Exception as e:
            return render(request, "emails/newsletter/base_newsletter.html", {
                "subject": "Error",
                "content": f"<p>❌ Failed to load sample data: {e}</p>",
                "site_domain": settings.SITE_URL,
                "unsubscribe_url": "#"
            })

        first_row.setdefault('site_domain', settings.SITE_URL)
        first_row.setdefault('unsubscribe_url', "#")
        first_row.setdefault('first_name', first_row.get('name', 'Friend'))
        first_row.setdefault('username', first_row.get('name', 'guest_user'))

        subject_template = Template(campaign.subject)
        body_template = Template(campaign.html_body)

        context = {
            "subject": subject_template.render(Context(first_row)),
            "content": body_template.render(Context(first_row)),
            **first_row
        }

        return render(request, "emails/newsletter/base_newsletter.html", context)


# Unsubscribe HTML View -----------------------------------------------------------------
class UnsubscribeHTMLView(View):
    def get(self, request, token):
        try:
            user = validate_email_opt_token(token)
            user = get_object_or_404(CustomUser, user=user)
            if not user:
                return render(request, "communication/unsubscribe_failed.html", status=400)

            UnsubscribedUser.objects.get_or_create(user=user)
            profile_url = f"{settings.FRONTEND_BASE_URL}/"
            return render(request, "communication/unsubscribe_success.html", {
                "profile_url": profile_url
            })

        except Exception:
            return render(request, "communication/unsubscribe_failed.html", status=400)
        

# Resubscribe HTML View -----------------------------------------------------------------
class ResubscribeView(APIView):
    def get(self, request, token):
        user = validate_email_opt_token(token)
        if user:

            profile_url = f"{settings.FRONTEND_BASE_URL}/"
            UnsubscribedUser.objects.filter(user=user).delete()
            return render(request, "communication/resubscribe_success.html", {
                "user": user,
                "profile_url": profile_url
            })
        return render(request, "communication/resubscribe_failed.html", status=400)
    
    
# External Unsubscribe View -----------------------------------------------------------------
class ExternalUnsubscribeView(View):
    def get(self, request, token):
        contact = validate_external_email_token(token)
        if contact:
            contact.is_unsubscribed = True
            contact.save()
            return render(request, "communication/unsubscribe_success.html", {
                "profile_url": settings.SITE_URL
            })
        else:
            return render(request, "communication/unsubscribe_failed.html", {
                "profile_url": settings.SITE_URL
            }, status=400)
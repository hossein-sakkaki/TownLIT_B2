from rest_framework.views import APIView
from django.views import View
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.template import Template, Context
from django.utils import timezone

from .models import UnsubscribedUser, EmailTemplate, ExternalEmailCampaign, EmailCampaign
from utils.email.token_generator import (
    validate_email_opt_token, validate_external_email_token,
    generate_email_opt_token
)

from django.contrib.auth import get_user_model
from utils.common.file_reader import read_csv_or_json
from .constants import LAYOUT_BASE_SITE

CustomUser = get_user_model()


# Email Template Preview View --------------------------------------------------------
class EmailTemplatePreviewView(View):
    def get(self, request, pk):
        template = get_object_or_404(EmailTemplate, pk=pk)
        layout = template.layout or LAYOUT_BASE_SITE
        
        context = {
            'subject': template.subject_template,
            'content': template.body_template,
            'site_domain': settings.SITE_URL,
            'unsubscribe_url': '#'
        }
        return render(request, f'{layout}.html', context)
    

# Email Campaign Preview View --------------------------------------------------------
class EmailCampaignPreviewView(APIView):
    def get(self, request, pk):
        campaign = get_object_or_404(EmailCampaign, pk=pk)
        template = campaign.template

        content = campaign.custom_html or (campaign.template.body_template if campaign.template else "")
        layout = template.layout if template else LAYOUT_BASE_SITE
        context = {
            "subject": campaign.subject,
            "content": content,
            "site_domain": settings.SITE_URL,
            "unsubscribe_url": "#"
        }

        return render(request, f'{layout}.html', context)
    

# External Email Campaign Preview View ------------------------------------------------
class ExternalCampaignPreviewView(View):
    def get(self, request, pk):
        campaign = get_object_or_404(ExternalEmailCampaign, pk=pk)
        template = campaign.template
        layout = template.layout if template else LAYOUT_BASE_SITE

        try:
            with campaign.csv_file.open('rb') as f:
                rows = read_csv_or_json(f)
            if not rows:
                raise ValueError("No data found in uploaded file.")
            first_row = rows[0]
        except Exception as e:
            return render(request, f'{layout}.html', {
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

        return render(request, f'{layout}.html', context)


# Unsubscribe HTML View -----------------------------------------------------------------
class UnsubscribeHTMLView(View):
    def get(self, request, token):
        try:
            user_obj = validate_email_opt_token(token)

            if not user_obj:
                raise ValueError("Invalid or expired token.")

            if isinstance(user_obj, CustomUser):
                # Unsubscribe by linking to CustomUser
                UnsubscribedUser.objects.get_or_create(user=user_obj)
                resubscribe_token = generate_email_opt_token(user_obj.id)
            else:
                # Unsubscribe by email (AccessRequest)
                UnsubscribedUser.objects.get_or_create(email=user_obj.email)
                resubscribe_token = generate_email_opt_token(user_obj.id)

            context = {
                "profile_url": f"{settings.FRONTEND_BASE_URL}/",
                "user": user_obj,
                "site_domain": settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "current_year": timezone.now().year,
                "resubscribe_url": f"{settings.SITE_URL}/api/communication/resubscribe/{resubscribe_token}/",
            }
            return render(request, "api/communication/unsubscribe_success.html", context)

        except Exception:
            context = {
                "site_domain": settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "current_year": timezone.now().year,
                "support_email": "support@townlit.com",
            }
            return render(request, "api/communication/unsubscribe_failed.html", context, status=400)
        

# Resubscribe HTML View -----------------------------------------------------------------
class ResubscribeView(APIView):
    def get(self, request, token):
        try:
            user_obj = validate_email_opt_token(token)

            if not user_obj:
                raise ValueError("Invalid or expired token.")

            if isinstance(user_obj, CustomUser):
                # Remove UnsubscribedUser linked to CustomUser
                UnsubscribedUser.objects.filter(user=user_obj).delete()
                new_token = generate_email_opt_token(user_obj.id)
            else:
                # Remove UnsubscribedUser linked to email (AccessRequest)
                UnsubscribedUser.objects.filter(email=user_obj.email).delete()
                new_token = generate_email_opt_token(user_obj.id)

            context = {
                "profile_url": f"{settings.FRONTEND_BASE_URL}/",
                "user": user_obj,
                "first_name": getattr(user_obj, "name", "Friend"),
                "username": getattr(user_obj, "username", "access_request"),
                "site_domain": settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "current_year": timezone.now().year,
                "unsubscribe_url": f"{settings.SITE_URL}/api/communication/unsubscribe/{new_token}/",
            }
            return render(request, "api/communication/resubscribe_success.html", context)

        except Exception:
            context = {
                "site_domain": settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "current_year": timezone.now().year,
                "support_email": "support@townlit.com"
            }
            return render(request, "api/communication/resubscribe_failed.html", context, status=400)


    
    
# External Unsubscribe View -----------------------------------------------------------------
class ExternalUnsubscribeView(View):
    def get(self, request, token):
        contact = validate_external_email_token(token)
        if contact:
            contact.is_unsubscribed = True
            contact.save()
            return render(request, "api/communication/unsubscribe_success.html", {
                "profile_url": settings.SITE_URL
            })
        else:
            return render(request, "api/communication/unsubscribe_failed.html", {
                "profile_url": settings.SITE_URL
            }, status=400)
            
            

# ٍEmail Preview -----------------------------------------------------------------
def preview_reset_password(request):
    context = {
        "name": "Gabby",
        "site_domain": settings.SITE_URL,
        "logo_base_url": settings.EMAIL_LOGO_URL,
        # "current_year": timezone.now().year,
    }
    return render(request, "emails/feedback/feedback_received_email.html", context)
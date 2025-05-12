# communication/views.py
from rest_framework.views import APIView
from django.views import View
from django.shortcuts import get_object_or_404, render
from django.conf import settings



from .models import UnsubscribedUser, EmailTemplate
from utils.email.token_generator import decode_unsubscribe_token
from .models import EmailCampaign
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


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
    


class UnsubscribeHTMLView(View):
    def get(self, request, token):
        try:
            user_id = decode_unsubscribe_token(token)
            user = get_object_or_404(CustomUser, id=user_id)

            UnsubscribedUser.objects.get_or_create(user=user)

            profile_url = f"{settings.FRONTEND_BASE_URL}/"

            return render(request, "communication/unsubscribe_success.html", {
                "profile_url": profile_url
            })

        except Exception:
            return render(request, "communication/unsubscribe_failed.html", status=400)
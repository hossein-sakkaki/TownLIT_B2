# apps/communication/views/legacy.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.


from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.template import Context, Template
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from apps.communication.constants import LAYOUT_BASE_SITE
from apps.communication.models import ExternalEmailCampaign
from apps.communication.services import EmailPreferenceService
from utils.common.file_reader import read_csv_or_json
from utils.email.token_generator import validate_external_email_token


@method_decorator(staff_member_required, name="dispatch")
class ExternalCampaignPreviewView(View):
    def get(self, request, pk):
        campaign = get_object_or_404(
            ExternalEmailCampaign.objects.select_related("template"),
            pk=pk,
        )

        layout = (
            campaign.template.layout
            if campaign.template_id
            else LAYOUT_BASE_SITE
        )

        try:
            with campaign.csv_file.open("rb") as file_obj:
                rows = read_csv_or_json(file_obj)

            if not rows:
                raise ValueError("No data found in uploaded file.")

            sample = dict(rows[0])

        except Exception as error:
            return render(
                request,
                f"{layout}.html",
                {
                    "subject": "Preview Error",
                    "content": (
                        "<p>Unable to load sample data: "
                        f"{error}</p>"
                    ),
                    "site_domain": settings.SITE_URL,
                    "unsubscribe_url": "#",
                },
            )

        sample.setdefault("email", "preview@townlit.com")
        sample.setdefault("first_name", sample.get("name") or "Friend")
        sample.setdefault("username", sample.get("name") or "guest_user")
        sample.setdefault("site_domain", settings.SITE_URL)
        sample.setdefault("logo_base_url", settings.EMAIL_LOGO_URL)
        sample.setdefault("current_year", timezone.now().year)
        sample.setdefault("unsubscribe_url", "#")

        subject = Template(
            campaign.subject or ""
        ).render(Context(sample))

        body = Template(
            campaign.html_body or ""
        ).render(Context(sample))

        sample["subject"] = subject
        sample["content"] = body

        return render(
            request,
            f"{layout}.html",
            sample,
        )


class ExternalUnsubscribeView(View):
    def get(self, request, token):
        contact = validate_external_email_token(token)

        if not contact:
            return render(
                request,
                "api/communication/unsubscribe_failed.html",
                {
                    "profile_url": settings.SITE_URL,
                },
                status=400,
            )

        EmailPreferenceService().unsubscribe_legacy_external(contact)

        return render(
            request,
            "api/communication/unsubscribe_success.html",
            {
                "profile_url": settings.SITE_URL,
                "email": contact.email,
            },
        )


@staff_member_required
def preview_reset_password(request):
    """
    Legacy internal email preview endpoint.
    """

    return render(
        request,
        "emails/feedback/feedback_received_email.html",
        {
            "name": "Gabby",
            "site_domain": settings.SITE_URL,
            "logo_base_url": settings.EMAIL_LOGO_URL,
        },
    )
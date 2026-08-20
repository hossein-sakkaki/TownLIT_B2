# apps/communication/views/previews.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.


from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views import View

from apps.communication.models import EmailCampaign, EmailTemplate
from apps.communication.services import (
    CampaignRenderer,
    EmailRecipient,
    EmailTemplateRenderer,
)


@method_decorator(staff_member_required, name="dispatch")
class EmailCampaignPreviewView(View):
    def get(self, request, pk):
        campaign = get_object_or_404(
            EmailCampaign.objects.select_related(
                "template",
                "template__theme",
                "theme",
                "topic",
            ),
            pk=pk,
        )

        recipient = EmailRecipient(
            email=request.GET.get("email") or "preview@townlit.com",
            first_name=request.GET.get("first_name") or "Friend",
            username=request.GET.get("username") or "townlit_member",
            source="preview",
        )

        rendered = CampaignRenderer().render(
            campaign=campaign,
            recipient=recipient,
            preview=True,
        )

        return render(
            request,
            rendered.template_path,
            rendered.context,
        )


@method_decorator(staff_member_required, name="dispatch")
class EmailTemplatePreviewView(View):
    def get(self, request, pk):
        template = get_object_or_404(
            EmailTemplate.objects.select_related("theme"),
            pk=pk,
        )

        rendered = EmailTemplateRenderer().render(template)

        return render(
            request,
            rendered.template_path,
            rendered.context,
        )
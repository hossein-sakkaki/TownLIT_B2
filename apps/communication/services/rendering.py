# apps/communication/services/rendering.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-20.


from dataclasses import dataclass

from django.conf import settings
from django.template import Context, Template
from django.utils import timezone

from .block_renderer import EmailBlockRenderer
from .context import CampaignContextBuilder
from .exceptions import CampaignRenderError
from .tracking import EmailTrackingService


@dataclass(frozen=True)
class RenderedCampaignEmail:
    subject: str
    preheader: str
    body_html: str
    template_path: str
    context: dict


@dataclass(frozen=True)
class RenderedTemplateEmail:
    subject: str
    preheader: str
    body_html: str
    template_path: str
    context: dict


class CampaignRenderer:
    """
    Single rendering path for preview, test and real delivery.
    """

    def __init__(self):
        self.context_builder = CampaignContextBuilder()
        self.block_renderer = EmailBlockRenderer()
        self.tracking_service = EmailTrackingService()

    def render(self, *, campaign, recipient, preview=False, delivery=None):
        try:
            context = self.context_builder.build(
                campaign=campaign,
                recipient=recipient,
                preview=preview,
            )

            if campaign.template_id:
                context = {
                    **(campaign.template.default_context or {}),
                    **context,
                }

            subject = self._render_string(
                campaign.subject or self._template_subject(campaign),
                context,
            )
            preheader = self._render_string(
                campaign.preheader_text or self._template_preheader(campaign),
                context,
            )

            body_html = self._render_body(
                campaign=campaign,
                context=context,
            )

            if delivery and not preview:
                body_html = self.tracking_service.decorate_html(
                    html=body_html,
                    campaign=campaign,
                    delivery=delivery,
                )

            context["content"] = body_html
            context["preheader_text"] = preheader

            return RenderedCampaignEmail(
                subject=subject,
                preheader=preheader,
                body_html=body_html,
                template_path=f"{campaign.effective_layout}.html",
                context=context,
            )

        except Exception as error:
            raise CampaignRenderError(
                f"Unable to render campaign {campaign.id}: {error}"
            ) from error

    def _render_body(self, *, campaign, context):
        campaign_blocks = campaign.content_blocks.filter(
            is_enabled=True
        ).order_by("sort_order", "id")

        if campaign_blocks.exists():
            return self.block_renderer.render(
                campaign_blocks,
                context=context,
                theme=campaign.effective_theme,
            )

        if campaign.custom_html:
            return self._render_string(campaign.custom_html, context)

        if not campaign.template_id:
            return ""

        template_blocks = campaign.template.content_blocks.filter(
            is_enabled=True
        ).order_by("sort_order", "id")

        if template_blocks.exists():
            return self.block_renderer.render(
                template_blocks,
                context=context,
                theme=campaign.effective_theme,
            )

        return self._render_string(
            campaign.template.body_template or "",
            context,
        )

    def _template_subject(self, campaign):
        return campaign.template.subject_template if campaign.template_id else ""

    def _template_preheader(self, campaign):
        return campaign.template.preheader_template if campaign.template_id else ""

    def _render_string(self, value, context):
        if not value:
            return ""

        return Template(str(value)).render(Context(context))


class EmailTemplateRenderer:
    """
    Render reusable templates independently for admin preview.
    """

    def __init__(self):
        self.block_renderer = EmailBlockRenderer()

    def render(self, template):
        theme = template.theme

        context = {
            **(template.default_context or {}),
            "email": "preview@townlit.com",
            "first_name": "Friend",
            "username": "townlit_member",
            "user": None,
            "email_theme": theme,
            "site_domain": settings.SITE_URL,
            "logo_base_url": settings.EMAIL_LOGO_URL,
            "current_year": timezone.now().year,
            "unsubscribe_url": "#",
            "resubscribe_url": "#",
        }

        blocks = template.content_blocks.filter(
            is_enabled=True
        ).order_by("sort_order", "id")

        if blocks.exists():
            body_html = self.block_renderer.render(
                blocks,
                context=context,
                theme=theme,
            )
        else:
            body_html = Template(
                template.body_template or ""
            ).render(Context(context))

        subject = Template(
            template.subject_template or ""
        ).render(Context(context))

        preheader = Template(
            template.preheader_template or ""
        ).render(Context(context))

        context["content"] = body_html
        context["preheader_text"] = preheader

        layout = theme.layout if theme else template.layout

        return RenderedTemplateEmail(
            subject=subject,
            preheader=preheader,
            body_html=body_html,
            template_path=f"{layout}.html",
            context=context,
        )
from django import forms
from django.utils.safestring import mark_safe

from .models import EmailCampaign, EmailTemplate
from utils.email.template_context import validate_template_variables, ALLOWED_TEMPLATE_VARIABLES


class EmailCampaignAdminForm(forms.ModelForm):
    class Meta:
        model = EmailCampaign
        fields = '__all__'
        help_texts = {
            'ignore_unsubscribe': (
                "⚠️ Use this ONLY for legal, safety, or system-wide messages "
                "that MUST be delivered even to unsubscribed users. Do not use this for general newsletters."
            ),
            'custom_html': mark_safe(
                "You can use the following variables:<br>" +
                ", ".join(f"<code>{{{{ {var} }}}}</code>" for var in ALLOWED_TEMPLATE_VARIABLES)
            )
        }
        



class EmailTemplateAdminForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = '__all__'
        help_texts = {
            'body_template': mark_safe(
                "You can use the following variables:<br>" +
                ", ".join(f"<code>{{{{ {var} }}}}</code>" for var in ALLOWED_TEMPLATE_VARIABLES)
            )
        }

    def clean_body_template(self):
        body = self.cleaned_data['body_template']
        try:
            validate_template_variables(body)
        except ValueError as e:
            raise forms.ValidationError(f"Invalid variable(s) in template: {e}")
        return body
from django import forms
from django.utils.safestring import mark_safe

from .models import EmailCampaign, EmailTemplate, UnsubscribedUser
from utils.email.template_context import validate_template_variables, ALLOWED_TEMPLATE_VARIABLES
from .services import get_users_for_campaign


# Email Campaign Admin Form -----------------------------------------------------------
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = kwargs.get('instance')

        if instance and instance.pk and instance.target_group:
            try:
                # --- Retrieve users for this campaign ---
                users_qs = get_users_for_campaign(instance)

                # --- Safe count: works for QuerySet or list ---
                if hasattr(users_qs, "count"):
                    final_count = users_qs.count()
                else:
                    final_count = len(users_qs)

                # --- Retrieve unsubscribed users ---
                unsubscribed_ids = UnsubscribedUser.objects.values_list('user_id', flat=True)

                # --- Determine all users (safe queryset fallback) ---
                all_users = get_users_for_campaign(instance)

                # If result is list, convert to a queryset dynamically
                if not hasattr(all_users, "model"):
                    # Import here to avoid circular issues
                    from apps.moderation.models import AccessRequest
                    all_users = AccessRequest.objects.all()

                # If not ignoring unsubscribes, restrict to model queryset
                if not instance.ignore_unsubscribe:
                    all_users = all_users.model.objects.all()

                # --- Compute unsubscribed count safely ---
                full_filtered_users = all_users.exclude(id__in=unsubscribed_ids)
                unsub_count = all_users.count() - full_filtered_users.count()

                # --- Display result in admin help text ---
                self.fields['target_group'].help_text = mark_safe(
                    f"<strong>📊 Estimated recipients:</strong> <code>{final_count:,}</code> user(s)<br>"
                    f"<span style='color:#888;'>({unsub_count} unsubscribed user(s) in this group)</span>"
                )

            except Exception as e:
                # Show any unexpected error in admin UI
                self.fields['target_group'].help_text = (
                    f"⚠ Unable to count recipients due to error: {e}"
                )

            

# Email Template Admin Form -----------------------------------------------------------
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
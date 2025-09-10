# apps/profiles/admin_forms.py
from django import forms
from apps.profiles.models import MemberServiceType

class MemberServiceTypeAdminForm(forms.ModelForm):
    """
    Admin form: server-side validations for dates and sensitive policy.
    (No custom non-model fields; keep ModelAdmin read-only helpers in admin.py)
    """

    class Meta:
        model = MemberServiceType
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # small UX hints
        if "credential_url" in self.fields:
            self.fields["credential_url"].widget.attrs.update({"placeholder": "https://..."})

    def clean(self):
        cleaned = super().clean()
        inst = self.instance if self.instance and self.instance.pk else None

        service      = cleaned.get("service") or (inst and inst.service)
        is_sensitive = bool(getattr(service, "is_sensitive", False))

        issued_at  = cleaned.get("issued_at")
        expires_at = cleaned.get("expires_at")
        document   = cleaned.get("document") or (inst and getattr(inst, "document", None))
        issuer     = cleaned.get("credential_issuer") or (inst and getattr(inst, "credential_issuer", None))

        # date relation
        if issued_at and expires_at and expires_at < issued_at:
            self.add_error("expires_at", "Expiration date cannot be before issue date.")

        # sensitive policy: doc OR (issuer + issued_at)
        if is_sensitive:
            has_doc = bool(document)
            has_endorsement = bool(issuer) and bool(issued_at)
            if not (has_doc or has_endorsement):
                self.add_error("document", "Sensitive service requires a PDF document or (issuer + issued date).")

        return cleaned

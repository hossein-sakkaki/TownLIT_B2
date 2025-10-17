# apps/profiles/admin_forms.py
from django import forms
from apps.profiles.models import MemberServiceType, Member

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



from apps.profilesOrg.constants_denominations import CHURCH_BRANCH_CHOICES, CHURCH_FAMILY_CHOICES_ALL, FAMILIES_BY_BRANCH

class MemberAdminForm(forms.ModelForm):
    """
    Admin form for Member:
    - Enforce that denomination_family (if set) belongs to denomination_branch.
    - Dynamically filter family choices by currently selected branch.
    """

    class Meta:
        model = Member
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        # Keep default init
        super().__init__(*args, **kwargs)

        # --- Make branch required & family optional in admin UI ---
        self.fields["denomination_branch"].required = True
        self.fields["denomination_family"].required = False

        # --- Determine the current branch (POST > instance > None) ---
        # Helps when adding or changing object so we can filter families dropdown.
        branch_from_post = self.data.get("denomination_branch")
        if branch_from_post:
            current_branch = branch_from_post
        else:
            current_branch = getattr(self.instance, "denomination_branch", None)

        # --- Filter family choices by current branch if available ---
        if current_branch:
            allowed = FAMILIES_BY_BRANCH.get(current_branch, set())
            filtered = [c for c in CHURCH_FAMILY_CHOICES_ALL if c[0] in allowed]
        else:
            # No branch yet → show empty list to encourage first selecting a branch
            filtered = []

        self.fields["denomination_family"].choices = [("", "— Optional —")] + filtered

    def clean(self):
        cleaned = super().clean()
        branch = cleaned.get("denomination_branch")
        family = cleaned.get("denomination_family")

        # Validate family belongs to the branch (if family provided)
        if family:
            allowed = FAMILIES_BY_BRANCH.get(branch, set())
            if family not in allowed:
                self.add_error(
                    "denomination_family",
                    "Selected family does not belong to the chosen branch."
                )
        return cleaned
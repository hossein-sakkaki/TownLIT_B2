from django import forms
from django.forms import ModelForm

from .models import Member, Organization
from .models import OrganizationManager



        
# ORG Manager Form ---------------------------------------------------------------
# class OrganizationManagerForm(forms.ModelForm):
#     class Meta:
#         model = OrganizationManager
#         fields = ['organization', 'member', 'is_approved', 'access_level']
    
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         if self.instance and self.instance.organization_id:
#             self.fields['member'].queryset = Member.objects.filter(organization_memberships=self.instance.organization)
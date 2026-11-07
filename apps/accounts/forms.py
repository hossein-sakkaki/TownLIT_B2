# apps/accounts/forms.py
# TownLIT-Backend
#
# Original Created date: not recorded in source; verify with Git history.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# USER Form ----------------------------------------------------------------------
class UserCreationForm(forms.ModelForm):
    email = forms.EmailField(required=True, max_length=254)
    mobile_number = forms.CharField(required=False, max_length=20)
    birthday = forms.DateField(required=False)
    password = forms.CharField(label='Password', widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ['email', 'birthday']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if 'birthday' in self.cleaned_data:
            user.birthday = self.cleaned_data['birthday']
        if 'mobile_number' in self.cleaned_data:
            user.mobile_number = self.cleaned_data['mobile_number'] or None
        if commit:
            user.save()
        return user
    
    
    
# USER CHANGE Form -----------------------------------------------------------------
class UserChangeForm(forms.ModelForm):
    email = forms.EmailField(required=True, max_length=254, disabled=True)
    mobile_number = forms.CharField(required=False, max_length=20)
    birthday = forms.DateField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['birthday'].initial = self.instance.birthday
            self.fields['mobile_number'].initial = self.instance.mobile_number

    def save(self, commit=True):
        user = super().save(commit=False)
        if 'birthday' in self.cleaned_data:
            user.birthday = self.cleaned_data['birthday']
        if 'mobile_number' in self.cleaned_data:
            user.mobile_number = self.cleaned_data['mobile_number'] or None
        if commit:
            user.save()
            self.save_m2m()
        return user
    password = ReadOnlyPasswordHashField(help_text='If you want to change password <a href="../password">click here...</a>')

    class Meta:
        model = CustomUser
        fields = ['email', 'mobile_number', 'password',
                  'name', 'family', 'username', 'birthday', 'gender', 'country', 'city','image_name',
                  'is_active', 'is_admin', 'is_member', 'is_suspended', 'reports_count']

# Restricted admin forms deliberately have no decrypted birthday field.
class UserCreationRestrictedForm(forms.ModelForm):
    email = forms.EmailField(required=True, max_length=254)
    password = forms.CharField(label='Password', widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ['email']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class UserChangeRestrictedForm(forms.ModelForm):
    email = forms.EmailField(required=True, max_length=254, disabled=True)
    password = ReadOnlyPasswordHashField(
        help_text='If you want to change password <a href="../password">click here...</a>'
    )

    class Meta:
        model = CustomUser
        fields = [
            'email', 'password', 'name', 'family', 'username',
            'gender', 'country', 'city', 'image_name', 'is_active', 'is_admin',
            'is_member', 'is_suspended', 'reports_count',
        ]

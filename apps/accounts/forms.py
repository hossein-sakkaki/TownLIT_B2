from django import forms
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# USER Form ----------------------------------------------------------------------
class UserCreationForm(forms.ModelForm):
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
    
    
    
# USER CHANGE Form -----------------------------------------------------------------
class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(help_text='If you want to change password <a href="../password">click here...</a>')

    class Meta:
        model = CustomUser
        fields = ['email', 'mobile_number', 'password',
                  'name', 'family', 'username', 'birthday', 'gender', 'country', 'city','image_name',
                  'is_active', 'is_admin', 'is_member', 'is_suspended', 'reports_count']
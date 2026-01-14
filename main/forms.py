from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from .models import Employee


class EmployeeProfileForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["first_name", "last_name", "father_name", "phone", "pinfl"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ism"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Familiya"}),
            "father_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Otasining ismi"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Telefon"}),
            "pinfl": forms.TextInput(attrs={"class": "form-control", "placeholder": "Pinfl"}),
        }


class UserEmailForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"}),
        }


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["old_password"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Joriy parol",
        })
        self.fields["new_password1"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Yangi parol",
        })
        self.fields["new_password2"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Yangi parolni qayta kiriting",
        })

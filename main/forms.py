from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .models import *


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


class TechnicsForm(forms.ModelForm):
    class Meta:
        model = Technics
        fields = [
            "group", "category", "organization", "name",
            "parametr", "inventory", "serial",
            "mac", "ip", "year", "price"
        ]
        widgets = {
            "group": forms.Select(attrs={"class": "form-select", "required": True}),
            "category": forms.Select(attrs={"class": "form-select", "required": True}),
            "organization": forms.Select(attrs={"class": "form-select", "required": True}),

            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "nomi", "required": True}),
            "parametr": forms.TextInput(attrs={"class": "form-control", "placeholder": "parametr"}),
            "inventory": forms.TextInput(attrs={"class": "form-control", "placeholder": "inventory"}),
            "serial": forms.TextInput(attrs={"class": "form-control", "placeholder": "serial"}),
            "mac": forms.TextInput(attrs={"class": "form-control", "placeholder": "mac"}),
            "ip": forms.TextInput(attrs={"class": "form-control", "placeholder": "ip"}),
            "year": forms.TextInput(attrs={"class": "form-control", "placeholder": "yili"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "narxi"}),
        }


class ExtraTechnicsForm(forms.ModelForm):
    class Meta:
        model = Structure
        fields = [
            "category", "organization", "name",
            "parametr", "inventory", "serial",
            "year", "price"
        ]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select", "required": True}),
            "organization": forms.Select(attrs={"class": "form-select", "required": True}),

            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "nomi", "required": True}),
            "parametr": forms.TextInput(attrs={"class": "form-control", "placeholder": "parametr"}),
            "inventory": forms.TextInput(attrs={"class": "form-control", "placeholder": "inventory"}),
            "serial": forms.TextInput(attrs={"class": "form-control", "placeholder": "serial"}),
            "year": forms.TextInput(attrs={"class": "form-control", "placeholder": "yili"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "narxi"}),
        }


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = [
            "name", "code", "number",
            "category", "unit", "price", "year"
        ]
        widgets = {
            "unit": forms.Select(attrs={"class": "form-select", "required": True}),
            "category": forms.Select(attrs={"class": "form-select", "required": True}),

            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "nomi", "required": True}),
            "code": forms.TextInput(attrs={"class": "form-control", "placeholder": "code", "required": True}),
            "number": forms.NumberInput(attrs={"class": "form-control", "placeholder": "number", "required": True}),
            "price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "price", "required": True}),
            "year": forms.TextInput(attrs={"class": "form-control", "placeholder": "year"}),
        }
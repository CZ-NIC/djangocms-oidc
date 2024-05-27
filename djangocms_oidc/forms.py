from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .widgets import JsonDataTextarea


class OIDCDataForm(forms.ModelForm):

    class Meta:
        widgets = {
            "claims": JsonDataTextarea,
        }

    def clean_authorization_prompt(self):
        prompt = self.cleaned_data.get('authorization_prompt')
        if "none" in prompt and len(prompt) > 1:
            raise ValidationError(_('Item "No interaction" cannot be combined with others.'))
        return prompt


class OIDCHandoverDataForm(forms.ModelForm):

    class Meta:
        widgets = {
            "claims": JsonDataTextarea,
        }

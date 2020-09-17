from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _


class OIDCDataForm(forms.ModelForm):

    def clean_authorization_prompt(self):
        prompt = self.cleaned_data.get('authorization_prompt')
        if "none" in prompt and len(prompt) > 1:
            raise ValidationError(_('Item "No interaction" cannot be combined with others.'))
        return prompt

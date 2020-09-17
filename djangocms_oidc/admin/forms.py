from django import forms
from django.utils.translation import ugettext_lazy as _


class OIDCProviderForm(forms.ModelForm):

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('register_consumer') is None and (
                cleaned_data.get('client_id') is None or cleaned_data.get('client_secret') is None):
            self.add_error(
                'client_id', forms.ValidationError(_('The value is required if "Register consumer" is not set.')))
            self.add_error(
                'client_secret', forms.ValidationError(_('The value is required if "Register consumer" is not set.')))

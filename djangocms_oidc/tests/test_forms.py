from django.forms import modelform_factory
from django.test import SimpleTestCase

from djangocms_oidc.forms import OIDCDataForm
from djangocms_oidc.models import OIDCHandoverData


class TestOIDCDataForm(SimpleTestCase):

    def setUp(self):
        self.Form = modelform_factory(OIDCHandoverData, form=OIDCDataForm, fields=('authorization_prompt', ))

    def test_none_login(self):
        form = self.Form({'authorization_prompt': ['none', 'login']})
        self.assertEqual(form.errors, {
            'authorization_prompt': ['Item "No interaction" cannot be combined with others.']
        })

    def test_none(self):
        form = self.Form({'authorization_prompt': ['none']})
        self.assertTrue(form.is_valid())

    def test_consent_login(self):
        form = self.Form({'authorization_prompt': ['consent', 'login']})
        self.assertTrue(form.is_valid())

from django.contrib.admin.sites import site
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from djangocms_oidc.admin.options import OIDCProviderAdmin
from djangocms_oidc.models import OIDCProvider, OIDCRegisterConsumer


class TestAdminForms(TestCase):

    post = {
        'name': 'Name',
        'slug': 'name',
        'authorization_endpoint': 'https://foo.foo/auth',
        'token_endpoint': 'https://foo.foo/token',
        'user_endpoint': 'https://foo.foo/user',
    }
    error_message = {
        'client_id': ['The value is required if "Register consumer" is not set.'],
        'client_secret': ['The value is required if "Register consumer" is not set.'],
    }

    def get_form(self):
        provider_admin = OIDCProviderAdmin(admin_site=site, model=OIDCProvider)
        request = RequestFactory().request()
        request.user = AnonymousUser()
        return provider_admin.get_form(request)

    def test_form(self):
        post = self.post.copy()
        post.update({
            'client_id': '42',
            'client_secret': 'secret',
        })
        OIDCProviderForm = self.get_form()
        form = OIDCProviderForm(post)
        self.assertTrue(form.is_valid())

    def test_form_client_id_missing(self):
        post = self.post.copy()
        post['client_secret'] = 'secret'
        OIDCProviderForm = self.get_form()
        form = OIDCProviderForm(post)
        self.assertEqual(form.errors, self.error_message)

    def test_form_client_secret_missing(self):
        post = self.post.copy()
        post['client_id'] = '42'
        OIDCProviderForm = self.get_form()
        form = OIDCProviderForm(post)
        self.assertEqual(form.errors, self.error_message)

    def test_form_with_register_consumer(self):
        post = self.post.copy()
        post['register_consumer'] = OIDCRegisterConsumer.objects.create(register_url="https://foo.foo/reg")
        OIDCProviderForm = self.get_form()
        form = OIDCProviderForm(post)
        self.assertTrue(form.is_valid())

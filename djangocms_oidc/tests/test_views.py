from collections import OrderedDict
from unittest.mock import patch
from urllib.parse import urlencode

import requests_mock
from cms.api import create_page
from cms.test_utils.testcases import CMSTestCase
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.core import cache
from django.http import JsonResponse
from django.test import RequestFactory, override_settings
from django.urls import reverse
from freezegun import freeze_time

from djangocms_oidc.constants import DJANGOCMS_PLUGIN_SESSION_KEY, DJANGOCMS_USER_SESSION_KEY
from djangocms_oidc.models import OIDCHandoverData, OIDCIdentifier, OIDCLogin, OIDCProvider, OIDCRegisterConsumer
from djangocms_oidc.views import DjangocmsOIDCAuthenticationCallbackView, DjangocmsOIDCAuthenticationRequestView


class CollectMessagesMixin:

    def _get_messages(self, request):
        return [(msg.level, msg.message) for msg in get_messages(request)]


@override_settings(CMS_CACHE_PREFIX='prefix:')
@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class TestOIDCSignupView(CollectMessagesMixin, CMSTestCase):

    consumer_registration = {
        'client_id': '1d9G0Oid4E5V',
        'client_secret': '5ed3a93b14cb5f1fdb97cb3dde1daddade443753eeb84432320b78a2',
        'expires_at': 'never'
    }

    @classmethod
    def setUpTestData(cls):
        cls.register_consumer = OIDCRegisterConsumer.objects.create(
            name="Test", register_url="https://foo.foo/register")
        cls.provider = OIDCProvider.objects.create(
            name="Provider", slug="provider", register_consumer=cls.register_consumer,
            authorization_endpoint="https://foo.foo/authorization-endpoint")
        cls.consumer = OIDCHandoverData.objects.create(provider=cls.provider, claims={})

    def setUp(self):
        cache.cache.clear()

    def test_signup_activation_failed(self):
        url = reverse('djangocms_oidc_signup', kwargs={'consumer_type': 'handover', 'plugin_id': 42})
        response = self.client.get(url)
        self.assertRedirects(response, '/')
        self.assertEqual(self._get_messages(response.wsgi_request), [
            (messages.ERROR, 'OIDC Consumer activation falied. Please try again.')
        ])
        data = cache.cache.get(f'prefix:djangocms_oidc_provider:{self.provider.pk}')
        self.assertIsNone(data)

    def test_signup_progress(self):
        cache.cache.set(f'prefix:djangocms_oidc_provider:{self.provider.pk}', '--PROGRESS--')
        url = reverse('djangocms_oidc_signup', kwargs={
            'consumer_type': self.consumer.consumer_type, 'plugin_id': self.consumer.pk})
        response = self.client.get(url)
        self.assertRedirects(response, '/')
        self.assertEqual(self._get_messages(response.wsgi_request), [
            (messages.INFO, 'Communication with the provider is in progress. Please try again later.')
        ])
        data = cache.cache.get(f'prefix:djangocms_oidc_provider:{self.provider.pk}')
        self.assertEqual(data, '--PROGRESS--')

    @requests_mock.Mocker()
    def test_provider_needs_register(self, mock_req):
        mock_req.post("https://foo.foo/register", text='Not Found', status_code=404)
        url = reverse('djangocms_oidc_signup', kwargs={
            'consumer_type': self.consumer.consumer_type, 'plugin_id': self.consumer.pk})
        response = self.client.get(url)
        self.assertRedirects(response, '/')
        self.assertEqual(self._get_messages(response.wsgi_request), [
            (messages.ERROR, 'Communication with the provider failed. Please try again later.'),
            (messages.ERROR, '404 Client Error: None for url: https://foo.foo/register'),
        ])
        data = cache.cache.get(f'prefix:djangocms_oidc_provider:{self.provider.pk}')
        self.assertEqual(data, '--PROGRESS--')

    @requests_mock.Mocker()
    def test_provider_make_registation(self, mock_req):
        mock_req.post("https://foo.foo/register", json={
            'client_secret_expires_at': 0,
            'client_secret': '5ed3a93b14cb5f1fdb97cb3dde1daddade443753eeb84432320b78a2',
            'client_id': '1d9G0Oid4E5V'
        })
        url = reverse('djangocms_oidc_signup', kwargs={
            'consumer_type': self.consumer.consumer_type, 'plugin_id': self.consumer.pk, 'prompt': 'login'})
        response = self.client.get(url)
        self.assertRedirects(response, "{}?next=/&prompt=login".format(reverse("oidc_authentication_init")),
                             target_status_code=302)
        self.assertEqual(self._get_messages(response.wsgi_request), [])
        data = cache.cache.get(f'prefix:djangocms_oidc_provider:{self.provider.pk}')
        self.assertEqual(data, self.consumer_registration)

    def test_provider_already_registered(self):
        cache.cache.set(f'prefix:djangocms_oidc_provider:{self.provider.pk}', self.consumer_registration)
        url = reverse('djangocms_oidc_signup', kwargs={
            'consumer_type': self.consumer.consumer_type, 'plugin_id': self.consumer.pk})
        session = self.client.session
        session[DJANGOCMS_USER_SESSION_KEY] = 42
        session.save()
        response = self.client.get(url)
        self.assertIsNone(self.client.session.get(DJANGOCMS_USER_SESSION_KEY))
        self.assertRedirects(response, "{}?next=/".format(reverse("oidc_authentication_init")), target_status_code=302)
        self.assertEqual(self._get_messages(response.wsgi_request), [])
        data = cache.cache.get(f'prefix:djangocms_oidc_provider:{self.provider.pk}')
        self.assertEqual(data, self.consumer_registration)


class TestOIDCDismissView(CMSTestCase):

    def test_dismiss(self):
        url = reverse('djangocms_oidc_dismiss')
        response = self.client.get(url)
        self.assertRedirects(response, '/')

    def test_dismiss_plugin_key(self):
        url = reverse('djangocms_oidc_dismiss')
        session = self.client.session
        session[DJANGOCMS_PLUGIN_SESSION_KEY] = 42
        session.save()
        response = self.client.get(url)
        self.assertRedirects(response, '/')
        self.assertIsNone(self.client.session.get(DJANGOCMS_PLUGIN_SESSION_KEY))

    def test_dismiss_user_key(self):
        url = reverse('djangocms_oidc_dismiss')
        session = self.client.session
        session[DJANGOCMS_USER_SESSION_KEY] = 42
        session.save()
        response = self.client.get(url)
        self.assertRedirects(response, '/')
        self.assertIsNone(self.client.session.get(DJANGOCMS_USER_SESSION_KEY))


class TestOIDCLogoutView(CMSTestCase):

    def test_logout(self):
        url = reverse('djangocms_oidc_logout')
        response = self.client.get(url)
        self.assertRedirects(response, '/')

    def test_logout_authenticated_user(self):
        user = get_user_model().objects.create(username="user")
        self.client.force_login(user)
        url = reverse('djangocms_oidc_logout')
        response = self.client.get(url)
        self.assertRedirects(response, '/')
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class TestOIDCDeleteIdentifiersView(CollectMessagesMixin, CMSTestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create(username="user")
        cls.provider = OIDCProvider.objects.create(name="Provider", slug="provider")

    def test_empty_post(self):
        url = reverse('djangocms_oidc_delete_identifiers')
        response = self.client.post(url)
        self.assertRedirects(response, '/')
        self.assertEqual(self._get_messages(response.wsgi_request), [])

    def test_not_authenticated_user(self):
        url = reverse('djangocms_oidc_delete_identifiers')
        response = self.client.post(url, {"djangocms_oidc_delete_identifier": "yes"})
        self.assertRedirects(response, '/')
        self.assertEqual(self._get_messages(response.wsgi_request), [])

    def test_no_identifier_selected(self):
        self.client.force_login(self.user)
        url = reverse('djangocms_oidc_delete_identifiers')
        response = self.client.post(url, {
            "djangocms_oidc_delete_identifier": "yes",
            "form-TOTAL_FORMS": "0",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
        })
        self.assertRedirects(response, '/')
        self.assertEqual(self._get_messages(response.wsgi_request), [
            (messages.INFO, 'No identifier has been deleted. Check one to delete.'),
        ])

    def test_invlaid_post(self):
        self.client.force_login(self.user)
        url = reverse('djangocms_oidc_delete_identifiers')
        response = self.client.post(url, {
            "djangocms_oidc_delete_identifier": "yes",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "1000",
        })
        self.assertRedirects(response, '/')
        self.assertEqual(self._get_messages(response.wsgi_request), [
            (messages.ERROR, '* cmsplugin_ptr\n  * This field is required.'),
        ])

    def test_invlaid_post_ajax(self):
        self.client.force_login(self.user)
        url = reverse('djangocms_oidc_delete_identifiers')
        response = self.client.post(url, {
            "djangocms_oidc_delete_identifier": "yes",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "1000",
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.json(), {
            'result': 'ERROR',
            'messages': [{'cmsplugin_ptr': ['This field is required.']}],
        })
        self.assertEqual(self._get_messages(response.wsgi_request), [])

    def test_delete_identifier(self):
        other_user = get_user_model().objects.create(username="other")
        ident = OIDCIdentifier.objects.create(user=self.user, provider=self.provider, uident="1234567890")
        OIDCIdentifier.objects.create(user=other_user, provider=self.provider, uident="9876543210")
        self.client.force_login(self.user)
        url = reverse('djangocms_oidc_delete_identifiers')
        response = self.client.post(url, {
            "djangocms_oidc_delete_identifier": "yes",
            "form-0-cmsplugin_ptr": [ident.cmsplugin_ptr_id],
            "form-0-DELETE": "on",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "1000",
        })
        self.assertRedirects(response, '/')
        self.assertEqual(self._get_messages(response.wsgi_request), [
            (messages.SUCCESS, 'Identifier has been deleted.'),
        ])
        self.assertQuerysetEqual(OIDCIdentifier.objects.all().values_list('uident', flat=True), [
            '9876543210'], transform=str)

    def test_delete_identifier_by_ajax(self):
        other_user = get_user_model().objects.create(username="other")
        ident = OIDCIdentifier.objects.create(user=self.user, provider=self.provider, uident="1234567890")
        OIDCIdentifier.objects.create(user=other_user, provider=self.provider, uident="9876543210")
        self.client.force_login(self.user)
        url = reverse('djangocms_oidc_delete_identifiers')
        response = self.client.post(url, {
            "djangocms_oidc_delete_identifier": "yes",
            "form-0-cmsplugin_ptr": [ident.cmsplugin_ptr_id],
            "form-0-DELETE": "on",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "1000",
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.json(), {'result': 'SUCCESS', 'messages': ['Identifier has been deleted.']})
        self.assertEqual(self._get_messages(response.wsgi_request), [])


class CreateRequestMixin:

    def _create_request(self):
        request = RequestFactory().request()
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request


@override_settings(CMS_CACHE_PREFIX='prefix:')
@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class TestDjangocmsOIDCAuthenticationRequestView(CreateRequestMixin, CollectMessagesMixin, CMSTestCase):

    @classmethod
    def setUpTestData(cls):
        cls.provider = OIDCProvider.objects.create(
            name="Provider", slug="provider", client_id="1234567890", client_secret="secret",
            authorization_endpoint="https://foo.foo/authorization-endpoint")
        cls.consumer = OIDCHandoverData.objects.create(provider=cls.provider, claims={})

    def setUp(self):
        cache.cache.clear()

    def _create_request_get(self, params):
        request = RequestFactory().get(params)
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_consumer_activation_falied(self):
        request = self._create_request()
        view = DjangocmsOIDCAuthenticationRequestView.as_view()
        response = view(request)
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertEqual(self._get_messages(request), [
            (messages.ERROR, 'OIDC Consumer activation falied. Please try again.'),
        ])

    @freeze_time('2020-10-08 17:02:42')
    @patch('djangocms_oidc.views.get_random_string')
    def test_consumer(self, mock_views_random):
        mock_views_random.return_value = 'random'
        request = self._create_request()
        request.session[DJANGOCMS_PLUGIN_SESSION_KEY] = ('handover', self.consumer.pk)
        view = DjangocmsOIDCAuthenticationRequestView.as_view()
        response = view(request)
        self.assertEqual(self._get_messages(request), [])
        self.assertEqual(request.session.get('oidc_nonce'), 'random')
        self.assertIsNone(request.session.get('oidc_login_next'))
        self.assertEqual(request.session.get('oidc_states'), {'random': {'nonce': 'random', 'added_on': 1602176562.0}})
        query = OrderedDict([
            ('response_type', 'code'),
            ('scope', 'openid email'),
            ('client_id', '1234567890'),
            ('redirect_uri', 'http://testserver/callback/'),
            ('state', 'random'),
            ('nonce', 'random'),
            ('claims', '{}'),
        ])
        url = f"https://foo.foo/authorization-endpoint?{urlencode(query)}"
        self.assertRedirects(response, url, fetch_redirect_response=False)

    @override_settings(OIDC_USE_NONCE=False)
    @freeze_time('2020-10-08 17:02:42')
    @patch('djangocms_oidc.views.get_random_string')
    def test_consumer_nonce_none_and_redirect_page(self, mock_views_random):
        mock_views_random.return_value = 'random'
        cms_page = create_page('test', 'test_content_plugin.html', 'en', slug="test")
        self.consumer.redirect_page = cms_page
        self.consumer.save()
        request = self._create_request()
        request.session[DJANGOCMS_PLUGIN_SESSION_KEY] = ('handover', self.consumer.pk)
        view = DjangocmsOIDCAuthenticationRequestView.as_view()
        response = view(request)
        self.assertEqual(self._get_messages(request), [])
        self.assertIsNone(request.session.get('oidc_nonce'))
        self.assertEqual(request.session.get('oidc_login_next'), '/test/')
        self.assertEqual(request.session.get('oidc_states'), {'random': {'nonce': None, 'added_on': 1602176562.0}})
        query = OrderedDict([
            ('response_type', 'code'),
            ('scope', 'openid email'),
            ('client_id', '1234567890'),
            ('redirect_uri', 'http://testserver/callback/'),
            ('state', 'random'),
            ('claims', '{}'),
        ])
        url = f"https://foo.foo/authorization-endpoint?{urlencode(query)}"
        self.assertRedirects(response, url, fetch_redirect_response=False)

    def test_get_extra_params_consumer_is_none(self):
        request = self._create_request()
        authreq = DjangocmsOIDCAuthenticationRequestView()
        params = authreq.get_extra_params(request, None)
        self.assertEqual(params, {})

    @override_settings(OIDC_AUTH_REQUEST_EXTRA_PARAMS={'audience': 'some-api.example.com'})
    def test_get_extra_params_consumer_is_none_extra_params(self):
        request = self._create_request()
        authreq = DjangocmsOIDCAuthenticationRequestView()
        params = authreq.get_extra_params(request, None)
        self.assertEqual(params, {'audience': 'some-api.example.com'})

    def test_get_extra_params_consumer_with_claims(self):
        request = self._create_request()
        authreq = DjangocmsOIDCAuthenticationRequestView()
        consumer = OIDCHandoverData.objects.create(provider=self.provider, claims={})
        consumer.claims = {'email': {'essential': True}}
        params = authreq.get_extra_params(request, consumer)
        self.assertEqual(params, {'claims': '{"email": {"essential": true}}'})

    def test_get_extra_params_authorization_prompt(self):
        request = self._create_request()
        authreq = DjangocmsOIDCAuthenticationRequestView()
        consumer = OIDCHandoverData.objects.create(provider=self.provider, claims={})
        consumer.claims = {'email': {'essential': True}}
        consumer.authorization_prompt = ['login']
        params = authreq.get_extra_params(request, consumer)
        self.assertEqual(params, {
            'claims': '{"email": {"essential": true}}',
            'prompt': 'login',
        })

    def test_get_extra_params_authorization_prompt_get(self):
        request = self._create_request_get('?prompt=consent,login,foo,none')
        authreq = DjangocmsOIDCAuthenticationRequestView()
        consumer = OIDCHandoverData.objects.create(provider=self.provider, claims={})
        consumer.claims = {'email': {'essential': True}}
        consumer.authorization_prompt = ['login']
        params = authreq.get_extra_params(request, consumer)
        self.assertEqual(sorted(params.keys()), sorted(['claims', 'prompt']))
        self.assertEqual(params['claims'], '{"email": {"essential": true}}')
        self.assertEqual(sorted(params['prompt'].split(' ')), ['consent', 'login'])

    def test_get_extra_params_authorization_prompt_get_none(self):
        request = self._create_request_get('?prompt=none')
        authreq = DjangocmsOIDCAuthenticationRequestView()
        consumer = OIDCHandoverData.objects.create(provider=self.provider, claims={})
        consumer.claims = {'email': {'essential': True}}
        params = authreq.get_extra_params(request, consumer)
        self.assertEqual(params, {
            'claims': '{"email": {"essential": true}}',
            'prompt': 'none',
        })


class TestDjangocmsOIDCAuthenticationCallbackView(CreateRequestMixin, CollectMessagesMixin, CMSTestCase):

    @classmethod
    def setUpTestData(cls):
        cls.provider = OIDCProvider.objects.create(
            name="Provider", slug="provider", client_id="1234567890", client_secret="secret",
            authorization_endpoint="https://foo.foo/authorization-endpoint")
        cls.consumer = OIDCLogin.objects.create(provider=cls.provider, claims={})

    def test_failure_url(self):
        callback = DjangocmsOIDCAuthenticationCallbackView()
        callback.request = self._create_request()
        self.assertEqual(callback.failure_url, '/')
        self.assertEqual(self._get_messages(callback.request), [])

    def test_failure_url_message(self):
        callback = DjangocmsOIDCAuthenticationCallbackView()
        callback.request = self._create_request()
        callback.request.session[DJANGOCMS_PLUGIN_SESSION_KEY] = ('login', self.consumer.pk)
        self.assertEqual(callback.failure_url, '/')
        self.assertEqual(self._get_messages(callback.request), [(messages.INFO, 'Login failed.')])


class TestTestingView(CMSTestCase):

    def test_homepage(self):
        response = self.client.get(reverse("test_home_page"))
        self.assertContains(response, 'Test Home page.')

    def test_login(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, 'Test Login page.')

    def test_fake_view(self):
        response = self.client.get(reverse("mdo_fake_view"))
        self.assertContains(response, 'Win!')

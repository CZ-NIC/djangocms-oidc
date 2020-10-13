import json
from unittest.mock import patch

import requests_mock
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from django.test import RequestFactory, TestCase, override_settings
from freezegun import freeze_time

from djangocms_oidc.auth import DjangocmsOIDCAuthenticationBackend
from djangocms_oidc.constants import DJNAGOCMS_PLUGIN_SESSION_KEY, DJNAGOCMS_USER_SESSION_KEY
from djangocms_oidc.models import OIDCHandoverData, OIDCIdentifier, OIDCLogin, OIDCProvider


class TestAuthBackend(TestCase):

    @override_settings(OIDC_RP_SIGN_ALGO='RS256')
    def test_invalid_config(self):
        with self.assertRaisesMessage(
                ImproperlyConfigured,
                "RS256 alg requires OIDC_RP_IDP_SIGN_KEY or OIDC_OP_JWKS_ENDPOINT to be configured."):
            DjangocmsOIDCAuthenticationBackend()

    def test_verify_claims(self):
        retval = DjangocmsOIDCAuthenticationBackend().verify_claims({'email': 'email@example.com'})
        self.assertTrue(retval)

    def test_verify_claims_failed(self):
        retval = DjangocmsOIDCAuthenticationBackend().verify_claims({})
        self.assertFalse(retval)

    @override_settings(OIDC_RP_SCOPES="")
    def test_verify_claims_no_scopes(self):
        retval = DjangocmsOIDCAuthenticationBackend().verify_claims({})
        self.assertTrue(retval)


class TestDjangocmsOIDCAuthenticationBackend(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.provider = OIDCProvider.objects.create(
            name="Provider", slug="provider", client_id="example_id", client_secret="client_secret",
            token_endpoint="https://foo.foo/token", user_endpoint="https://foo.foo/user")
        cls.plugin = OIDCHandoverData.objects.create(provider=cls.provider)

    @override_settings(OIDC_OP_TOKEN_ENDPOINT='https://server.example.com/token')
    @override_settings(OIDC_OP_USER_ENDPOINT='https://server.example.com/user')
    @override_settings(OIDC_RP_CLIENT_ID='example_id')
    @override_settings(OIDC_RP_CLIENT_SECRET='client_secret')
    def setUp(self):
        request = RequestFactory().request()
        request.session = {}
        self.backend = DjangocmsOIDCAuthenticationBackend()
        self.backend.request = request

    @override_settings(OIDC_USE_NONCE=True)
    @patch('mozilla_django_oidc.auth.OIDCAuthenticationBackend._verify_jws')
    def test_verify_token_failed_nonce(self, jws_mock):
        self.backend.request.session[DJNAGOCMS_PLUGIN_SESSION_KEY] = (self.plugin.consumer_type, self.plugin.pk)
        jws_mock.return_value = json.dumps({'nonce': 'foobar'}).encode('utf-8')
        with self.assertRaisesMessage(SuspiciousOperation, 'JWT Nonce verification failed.'):
            self.backend.verify_token('my_token', **{'nonce': 'foo'})
        jws_mock.assert_called_with(b'my_token', 'client_secret')

    @override_settings(OIDC_USE_NONCE=True)
    @patch('mozilla_django_oidc.auth.OIDCAuthenticationBackend._verify_jws')
    def test_verify_token(self, jws_mock):
        self.backend.request.session[DJNAGOCMS_PLUGIN_SESSION_KEY] = (self.plugin.consumer_type, self.plugin.pk)
        jws_mock.return_value = json.dumps({'nonce': 'foobar'}).encode('utf-8')
        payload = self.backend.verify_token('my_token', **{'nonce': 'foobar'})
        jws_mock.assert_called_with(b'my_token', 'client_secret')
        self.assertEqual(payload, {'nonce': 'foobar'})

    def test_verify_token_no_consumer(self):
        payload = self.backend.verify_token('my_token', **{'nonce': 'foobar'})
        self.assertEqual(payload, {})

    def test_get_token_no_consumer(self):
        response = self.backend.get_token({})
        self.assertEqual(response, {})

    @requests_mock.Mocker()
    def test_get_token(self, mock_req):
        mock_req.post("https://foo.foo/token", json={'status': 'OK'})
        self.backend.request.session[DJNAGOCMS_PLUGIN_SESSION_KEY] = (self.plugin.consumer_type, self.plugin.pk)
        response = self.backend.get_token({})
        self.assertEqual(response, {'status': 'OK'})

    @override_settings(OIDC_TOKEN_USE_BASIC_AUTH=True)
    def test_get_token_use_basic_auth(self):
        response = self.backend.get_token({'client_id': '42', 'client_secret': 'secret'})
        self.assertEqual(response, {})

    def test_get_userinfo_no_consumer(self):
        response = self.backend.get_userinfo('access_token', 'id_token', {})
        self.assertEqual(response, {})

    @requests_mock.Mocker()
    def test_get_userinfo(self, mock_req):
        mock_req.get("https://foo.foo/user", json={'status': 'OK'})
        self.backend.request.session[DJNAGOCMS_PLUGIN_SESSION_KEY] = (self.plugin.consumer_type, self.plugin.pk)
        response = self.backend.get_userinfo('access_token', 'id_token', {})
        self.assertEqual(response, {'status': 'OK'})

    def test_authenticate_no_request(self):
        self.assertIsNone(self.backend.authenticate(None))

    @requests_mock.Mocker()
    @patch('mozilla_django_oidc.auth.OIDCAuthenticationBackend._verify_jws')
    def test_authenticate(self, mock_req, jws_mock):
        jws_mock.return_value = json.dumps({'nonce': 'foobar'}).encode('utf-8')
        mock_req.post("https://foo.foo/token", json={'id_token': '42', 'access_token': 'ok'})
        mock_req.get("https://foo.foo/user", json={'email': 'user@foo.foo'})
        request = RequestFactory().get("/?state=ok&code=42")
        request.session = {
            DJNAGOCMS_PLUGIN_SESSION_KEY: (self.plugin.consumer_type, self.plugin.pk)
        }
        self.backend.request = request
        self.assertIsNone(self.backend.authenticate(request, nonce='foobar'))
        self.assertEqual(request.session[DJNAGOCMS_USER_SESSION_KEY]['email'], 'user@foo.foo')

    def test_authenticate_no_code(self):
        request = RequestFactory().get("/?state=ok")
        self.backend.request = request
        self.assertIsNone(self.backend.authenticate(request))

    @requests_mock.Mocker()
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.verify_token")
    def test_authenticate_no_payload(self, mock_req, mock_verify_token):
        mock_req.post("https://foo.foo/token", json={'id_token': '42', 'access_token': 'ok'})
        mock_verify_token.return_value = None
        request = RequestFactory().get("/?state=ok&code=42")
        request.session = {
            DJNAGOCMS_PLUGIN_SESSION_KEY: (self.plugin.consumer_type, self.plugin.pk)
        }
        self.backend.request = request
        self.assertIsNone(self.backend.authenticate(request, nonce='foobar'))
        mock_verify_token.assert_called_with('42', nonce='foobar')

    @requests_mock.Mocker()
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.verify_token")
    def test_authenticate_suspicious_operation(self, mock_req, mock_verify_token):
        mock_req.post("https://foo.foo/token", json={'id_token': '42', 'access_token': 'ok'})
        mock_req.get("https://foo.foo/user", exc=SuspiciousOperation)
        mock_verify_token.return_value = {'status': 'foo'}
        request = RequestFactory().get("/?state=ok&code=42")
        request.session = {
            DJNAGOCMS_PLUGIN_SESSION_KEY: (self.plugin.consumer_type, self.plugin.pk)
        }
        self.backend.request = request
        self.assertIsNone(self.backend.authenticate(request, nonce='foobar'))
        mock_verify_token.assert_called_with('42', nonce='foobar')

    @override_settings(OIDC_RP_SIGN_ALGO='RS256')
    @override_settings(OIDC_RP_IDP_SIGN_KEY='key')
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.get_payload_data")
    def test_verify_token_algo_sign_key(self, mock_get_payload_data):
        mock_get_payload_data.return_value = json.dumps({'nonce': 'foobar'}).encode('utf-8')
        backend = DjangocmsOIDCAuthenticationBackend()
        backend.request = self.backend.request
        response = backend.verify_token('1234567980', nonce="foobar")
        self.assertEqual(response, {'nonce': 'foobar'})
        mock_get_payload_data.assert_called_with(b'1234567980', 'key')

    @override_settings(OIDC_RP_SIGN_ALGO='RS256')
    @override_settings(OIDC_RP_IDP_SIGN_KEY=None)
    @override_settings(OIDC_OP_JWKS_ENDPOINT="https://foo.foo/jwk-endpoint")
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.retrieve_matching_jwk")
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.get_payload_data")
    def test_verify_token_algo_sign_key_is_none(self, mock_get_payload_data, mock_retrieve_matching_jwk):
        mock_get_payload_data.return_value = json.dumps({'nonce': 'foobar'}).encode('utf-8')
        mock_retrieve_matching_jwk.return_value = 'key'
        backend = DjangocmsOIDCAuthenticationBackend()
        backend.request = self.backend.request
        response = backend.verify_token('1234567980', nonce="foobar")
        self.assertEqual(response, {'nonce': 'foobar'})
        mock_get_payload_data.assert_called_with(b'1234567980', 'key')
        mock_retrieve_matching_jwk.assert_called_with(b'1234567980')

    @requests_mock.Mocker()
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.verify_claims")
    def test_get_or_create_user_no_claims_verified(self, mock_req, mock_verify_claims):
        mock_req.get("https://foo.foo/user", json={'status': 'OK'})
        mock_verify_claims.return_value = False
        self.backend.request.session[DJNAGOCMS_PLUGIN_SESSION_KEY] = (self.plugin.consumer_type, self.plugin.pk)
        with self.assertRaisesMessage(SuspiciousOperation, "Claims verification failed"):
            self.backend.get_or_create_user(self.backend.request, 'access_token', 'id_token', {'status': 'foo'})
        mock_verify_claims.assert_called_with({'status': 'OK'})

    def _get_messages(self, request):
        return [(msg.level, msg.message) for msg in get_messages(request)]

    @requests_mock.Mocker()
    @patch("djangocms_oidc.helpers.get_consumer")
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.verify_claims")
    def test_get_or_create_user_consumer_is_none(self, mock_req, mock_verify_claims, mock_get_consumer):
        mock_req.get("https://foo.foo/user", json={'status': 'OK'})
        mock_verify_claims.return_value = True
        mock_get_consumer.side_effect = [(self.plugin.consumer_type, self.plugin.pk), None]
        self.backend.request._messages = FallbackStorage(self.backend.request)
        response = self.backend.get_or_create_user(self.backend.request, 'access_token', 'id_token', {'status': 'foo'})
        self.assertIsNone(response)
        mock_verify_claims.assert_called_with({})
        self.assertEqual(self._get_messages(self.backend.request), [
            (messages.ERROR, 'OIDC Consumer activation failed during authentication. Please try again.')
        ])

    @requests_mock.Mocker()
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.verify_claims")
    def test_get_or_create_user_consumer_insist(self, mock_req, mock_verify_claims):
        mock_req.get("https://foo.foo/user", json={'status': 'OK'})
        mock_verify_claims.return_value = True
        claims = {
            'userinfo': {'email': {'essential': True}},
        }
        plugin = OIDCHandoverData.objects.create(provider=self.provider, insist_on_required_claims=True, claims=claims)
        self.backend.request.session[DJNAGOCMS_PLUGIN_SESSION_KEY] = (plugin.consumer_type, plugin.pk)
        self.backend.request._messages = FallbackStorage(self.backend.request)
        response = self.backend.get_or_create_user(self.backend.request, 'access_token', 'id_token', {'status': 'foo'})
        self.assertIsNone(response)
        mock_verify_claims.assert_called_with({'status': 'OK'})
        self.assertEqual(self._get_messages(self.backend.request), [
            (messages.ERROR, 'Not all required data has been handovered. Please make the transfer again and select all'
                             ' the required values.')
        ])

    @freeze_time('2020-10-12 18:55:42')
    @requests_mock.Mocker()
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.verify_claims")
    def test_get_or_create_user_consumer_can_login(self, mock_req, mock_verify_claims):
        mock_req.get("https://foo.foo/user", json={'email': 'foo@foo.foo'})
        mock_verify_claims.return_value = True
        plugin = OIDCLogin.objects.create(provider=self.provider, insist_on_required_claims=True)
        self.backend.request.session[DJNAGOCMS_PLUGIN_SESSION_KEY] = (plugin.consumer_type, plugin.pk)
        self.backend.request._messages = FallbackStorage(self.backend.request)
        self.backend.request.user = AnonymousUser()
        user = get_user_model().objects.create(username="user", email='foo@foo.foo')
        response = self.backend.get_or_create_user(self.backend.request, 'access_token', 'id_token', {'status': 'foo'})
        self.assertEqual(response, user)
        mock_verify_claims.assert_called_with({'email': 'foo@foo.foo', 'user_info_created_at': 1602528942.0})
        self.assertFalse(OIDCIdentifier.objects.filter(user=user).exists())
        self.assertEqual(self._get_messages(self.backend.request), [])

    @freeze_time('2020-10-12 18:55:42')
    @requests_mock.Mocker()
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.verify_claims")
    def test_get_or_create_user_is_authenticated(self, mock_req, mock_verify_claims):
        mock_req.get("https://foo.foo/user", json={'email': 'foo@foo.foo'})
        mock_verify_claims.return_value = True
        plugin = OIDCLogin.objects.create(provider=self.provider, insist_on_required_claims=True)
        self.backend.request.session[DJNAGOCMS_PLUGIN_SESSION_KEY] = (plugin.consumer_type, plugin.pk)
        self.backend.request._messages = FallbackStorage(self.backend.request)
        user = get_user_model().objects.create(username="user", email='foo@foo.foo')
        self.backend.request.user = user
        response = self.backend.get_or_create_user(self.backend.request, 'access_token', 'id_token', {'status': 'foo'})
        self.assertEqual(response, user)
        mock_verify_claims.assert_called_with({'email': 'foo@foo.foo', 'user_info_created_at': 1602528942.0})
        self.assertFalse(OIDCIdentifier.objects.filter(user=user).exists())
        self.assertEqual(self._get_messages(self.backend.request), [])

    @freeze_time('2020-10-12 18:55:42')
    @requests_mock.Mocker()
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.verify_claims")
    def test_get_or_create_user_is_authenticated_with_openid2_id(self, mock_req, mock_verify_claims):
        mock_req.get("https://foo.foo/user", json={'email': 'foo@foo.foo', 'openid2_id': 'oid'})
        mock_verify_claims.return_value = True
        plugin = OIDCLogin.objects.create(provider=self.provider, insist_on_required_claims=True)
        self.backend.request.session[DJNAGOCMS_PLUGIN_SESSION_KEY] = (plugin.consumer_type, plugin.pk)
        self.backend.request._messages = FallbackStorage(self.backend.request)
        user = get_user_model().objects.create(username="user", email='foo@foo.foo')
        self.backend.request.user = user
        response = self.backend.get_or_create_user(self.backend.request, 'access_token', 'id_token', {'status': 'foo'})
        self.assertEqual(response, user)
        mock_verify_claims.assert_called_with({
            'email': 'foo@foo.foo', 'openid2_id': 'oid', 'user_info_created_at': 1602528942.0})
        self.assertQuerysetEqual(OIDCIdentifier.objects.all().values_list('uident', flat=True), ['oid'], transform=str)
        self.assertEqual(self._get_messages(self.backend.request), [
            (messages.SUCCESS, 'The account has been successfully paired with the provider.')
        ])

    @freeze_time('2020-10-12 18:55:42')
    @requests_mock.Mocker()
    @patch("djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend.verify_claims")
    def test_get_or_create_user_is_authenticated_openid2_id_already_paired(self, mock_req, mock_verify_claims):
        mock_req.get("https://foo.foo/user", json={'email': 'foo@foo.foo', 'openid2_id': 'oid'})
        mock_verify_claims.return_value = True
        plugin = OIDCLogin.objects.create(provider=self.provider, insist_on_required_claims=True)
        self.backend.request.session[DJNAGOCMS_PLUGIN_SESSION_KEY] = (plugin.consumer_type, plugin.pk)
        self.backend.request._messages = FallbackStorage(self.backend.request)
        user = get_user_model().objects.create(username="user", email='foo@foo.foo')
        self.backend.request.user = user
        other_user = get_user_model().objects.create(username="other")
        OIDCIdentifier.objects.create(user=other_user, provider=self.provider, uident="oid")
        response = self.backend.get_or_create_user(self.backend.request, 'access_token', 'id_token', {'status': 'foo'})
        self.assertEqual(response, user)
        mock_verify_claims.assert_called_with({
            'email': 'foo@foo.foo', 'openid2_id': 'oid', 'user_info_created_at': 1602528942.0})
        self.assertFalse(OIDCIdentifier.objects.filter(user=user).exists())
        self.assertEqual(self._get_messages(self.backend.request), [
            (messages.ERROR, 'Pairing cannot be performed. This identifier is already paired with another account.')
        ])

    def test_create_identifier_if_missing(self):
        openid2_id = "openid2_id"
        user = get_user_model().objects.create(username="user")
        OIDCIdentifier.objects.create(user=user, provider=self.provider, uident=openid2_id)
        self.backend.create_identifier_if_missing(self.backend.request, user, self.provider, openid2_id)
        self.assertQuerysetEqual(OIDCIdentifier.objects.all().values_list('uident', flat=True), [openid2_id],
                                 transform=str)

    def test_not_authenticated_user_zero(self):
        user = get_user_model().objects.create(username="user", email='foo@foo.foo')
        user_info = {'email': 'unknown@foo.foo'}
        self.backend.request._messages = FallbackStorage(self.backend.request)
        response = self.backend.not_authenticated_user(self.backend.request, user_info, self.plugin)
        self.assertIsNone(response)
        self.assertFalse(OIDCIdentifier.objects.filter(user=user).exists())
        self.assertEqual(self._get_messages(self.backend.request), [])

    def test_not_authenticated_user_zero_with_openid2_id(self):
        user = get_user_model().objects.create(username="user", email='foo@foo.foo')
        user_info = {'email': 'unknown@foo.foo', 'openid2_id': '4242'}
        self.backend.request._messages = FallbackStorage(self.backend.request)
        response = self.backend.not_authenticated_user(self.backend.request, user_info, self.plugin)
        self.assertIsNone(response)
        self.assertFalse(OIDCIdentifier.objects.filter(user=user).exists())
        self.assertEqual(self._get_messages(self.backend.request), [])

    def test_not_authenticated_user_one(self):
        user = get_user_model().objects.create(username="user", email='foo@foo.foo')
        user_info = {'email': user.email}
        self.backend.request._messages = FallbackStorage(self.backend.request)
        response = self.backend.not_authenticated_user(self.backend.request, user_info, self.plugin)
        self.assertEqual(response, user)
        self.assertFalse(OIDCIdentifier.objects.filter(user=user).exists())
        self.assertEqual(self._get_messages(self.backend.request), [])

    def test_not_authenticated_user_one_with_openid2_id(self):
        user = get_user_model().objects.create(username="user", email='foo@foo.foo')
        user_info = {'email': user.email, 'openid2_id': '4242'}
        self.backend.request._messages = FallbackStorage(self.backend.request)
        response = self.backend.not_authenticated_user(self.backend.request, user_info, self.plugin)
        self.assertEqual(response, user)
        self.assertQuerysetEqual(OIDCIdentifier.objects.filter(user=user).values_list('uident', flat=True), ['4242'],
                                 transform=str)
        self.assertEqual(self._get_messages(self.backend.request), [
            (messages.SUCCESS, 'The account has been successfully paired with the provider.')
        ])

    def test_not_authenticated_user_one_user_is_not_active(self):
        user = get_user_model().objects.create(username="user", email='foo@foo.foo', is_active=False)
        user_info = {'email': user.email, 'openid2_id': '4242'}
        self.backend.request._messages = FallbackStorage(self.backend.request)
        response = self.backend.not_authenticated_user(self.backend.request, user_info, self.plugin)
        self.assertIsNone(response)
        self.assertQuerysetEqual(OIDCIdentifier.objects.filter(user=user).values_list('uident', flat=True), ['4242'],
                                 transform=str)
        self.assertEqual(self._get_messages(self.backend.request), [
            (messages.SUCCESS, 'The account has been successfully paired with the provider.'),
            (messages.ERROR, 'Your account is deactivated. Please contact our support.'),
        ])

    def test_not_authenticated_user_more_than_one(self):
        User = get_user_model()
        User.objects.create(username="user1", email='foo@foo.foo')
        User.objects.create(username="user2", email='foo@foo.foo')
        user_info = {'email': 'foo@foo.foo'}
        self.backend.request._messages = FallbackStorage(self.backend.request)
        with self.assertRaisesMessage(SuspiciousOperation, 'Multiple users returned'):
            self.backend.not_authenticated_user(self.backend.request, user_info, self.plugin)

    def test_not_authenticated_user_can_login(self):
        plugin = OIDCLogin.objects.create(provider=self.provider)
        user_info = {'email': 'foo@foo.foo'}
        self.backend.request._messages = FallbackStorage(self.backend.request)
        response = self.backend.not_authenticated_user(self.backend.request, user_info, plugin)
        user = get_user_model().objects.get(email='foo@foo.foo')
        self.assertEqual(response, user)
        self.assertQuerysetEqual(OIDCIdentifier.objects.all(), [])
        self.assertEqual(self._get_messages(self.backend.request), [
            (messages.SUCCESS, 'A new account has been created with the username '
                               'aLOwvSRJuFVqFX111xmv5vYGuXk and email foo@foo.foo.'),
        ])

    def test_not_authenticated_user_can_login_with_openid2_id(self):
        plugin = OIDCLogin.objects.create(provider=self.provider)
        user_info = {'email': 'foo@foo.foo', 'openid2_id': '4242'}
        self.backend.request._messages = FallbackStorage(self.backend.request)
        response = self.backend.not_authenticated_user(self.backend.request, user_info, plugin)
        user = get_user_model().objects.get(email='foo@foo.foo')
        self.assertEqual(response, user)
        self.assertQuerysetEqual(OIDCIdentifier.objects.filter(user=user).values_list('uident', flat=True), ['4242'],
                                 transform=str)
        self.assertEqual(self._get_messages(self.backend.request), [
            (messages.SUCCESS, 'A new account has been created with the username '
                               'aLOwvSRJuFVqFX111xmv5vYGuXk and email foo@foo.foo.'),
        ])

    def test_not_authenticated_user_can_login_no_new_user(self):
        plugin = OIDCLogin.objects.create(provider=self.provider, no_new_user=True)
        user_info = {'email': 'foo@foo.foo'}
        self.backend.request._messages = FallbackStorage(self.backend.request)
        response = self.backend.not_authenticated_user(self.backend.request, user_info, plugin)
        self.assertIsNone(response)
        self.assertEqual(self._get_messages(self.backend.request), [
            (messages.INFO, 'To pair with your identity provider, log in first.'),
        ])

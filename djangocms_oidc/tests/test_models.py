import datetime

import requests_mock
from django.core import cache
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from freezegun import freeze_time

from djangocms_oidc.models import (
    ConsumerRegistrationExpired,
    OIDCDisplayDedicatedContent,
    OIDCHandoverData,
    OIDCProvider,
    OIDCRegisterConsumer,
    OIDCShowAttribute,
    validate_claims,
)


class TestOIDCRegisterConsumer(SimpleTestCase):

    def test_str(self):
        consumer = OIDCRegisterConsumer(name="Test")
        self.assertEqual(str(consumer), 'Test')

    def test_get_payload(self):
        consumer = OIDCRegisterConsumer(name="Test")
        payload = consumer.get_payload('The Name', ['https://foo.foo/1', 'https://foo.foo/2'])
        self.assertEqual(payload, {
            'application_type': 'web',
            'id_token_signed_response_alg': 'HS256',
            'redirect_uris': ['https://foo.foo/1', 'https://foo.foo/2'],
            'token_endpoint_auth_method': 'client_secret_post',
            'response_types': ['code'],
            'client_name': 'The Name'
        })

    @requests_mock.Mocker()
    def test_make_registration(self, mock_req):
        mock_req.post("https://foo.foo/register", json={'status': 'OK'})
        consumer = OIDCRegisterConsumer(name="Test", register_url="https://foo.foo/register")
        response = consumer.make_registration('The Name', ['https://foo.foo/1', 'https://foo.foo/2'])
        self.assertEqual(response, {'status': 'OK'})


@override_settings(CMS_CACHE_PREFIX='prefix:')
@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class TestOIDCProvider(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.register_consumer = OIDCRegisterConsumer.objects.create(
            name="Test", register_url="https://foo.foo/register")

    def setUp(self):
        cache.cache.clear()

    def test_str(self):
        provider = OIDCProvider(name="Provider")
        self.assertEqual(str(provider), 'Provider')

    def test_get_client_id(self):
        provider = OIDCProvider(name="Provider", client_id="42")
        self.assertEqual(provider.get_client_id(), "42")

    def test_get_client_id_cache_expired(self):
        provider = OIDCProvider(name="Provider")
        with self.assertRaises(ConsumerRegistrationExpired):
            provider.get_client_id()

    def test_get_client_id_from_cache(self):
        provider = OIDCProvider.objects.create(name="Provider", slug="provider")
        cache.cache.set(f'prefix:djangocms_oidc_provider:{provider.pk}', {'client_id': 42})
        client_id = provider.get_client_id()
        self.assertEqual(client_id, 42)

    def test_get_client_secret(self):
        provider = OIDCProvider(name="Provider", client_secret="42")
        self.assertEqual(provider.get_client_secret(), "42")

    def test_get_client_secret_cache_expired(self):
        provider = OIDCProvider(name="Provider")
        with self.assertRaises(ConsumerRegistrationExpired):
            provider.get_client_secret()

    def test_get_client_secret_from_cache(self):
        provider = OIDCProvider.objects.create(name="Provider", slug="provider")
        cache.cache.set(f'prefix:djangocms_oidc_provider:{provider.pk}', {'client_secret': 42})
        get_client_secret = provider.get_client_secret()
        self.assertEqual(get_client_secret, 42)

    def test_needs_register(self):
        provider = OIDCProvider(name="Provider", client_id=42)
        self.assertFalse(provider.needs_register())

    def test_needs_register_from_cache(self):
        provider = OIDCProvider.objects.create(name="Provider", slug="provider")
        cache.cache.set(f'prefix:djangocms_oidc_provider:{provider.pk}', {'client_id': 42})
        self.assertFalse(provider.needs_register())

    def test_needs_register_is_true(self):
        provider = OIDCProvider(name="Provider")
        self.assertTrue(provider.needs_register())

    def test_get_cache_key(self):
        provider = OIDCProvider.objects.create(name="Provider", slug="provider")
        self.assertEqual(provider.get_cache_key(), f'prefix:djangocms_oidc_provider:{provider.pk}')

    def test_registration_in_progress_not(self):
        provider = OIDCProvider(name="Provider", client_id=42)
        self.assertFalse(provider.registration_in_progress())

    def test_registration_in_progress(self):
        provider = OIDCProvider.objects.create(name="Provider", slug="provider")
        cache.cache.set(f'prefix:djangocms_oidc_provider:{provider.pk}', '--PROGRESS--')
        self.assertTrue(provider.registration_in_progress())

    @requests_mock.Mocker()
    def test_register_consumer_into_cache_request_exception(self, mock_req):
        mock_req.post("https://foo.foo/register", text='Not Found', status_code=404)
        provider = OIDCProvider.objects.create(
            name="Provider", slug="provider", register_consumer=self.register_consumer)
        with freeze_time('2020-10-06 14:55') as frozen_datetime:
            msg = provider.register_consumer_into_cache(['https://foo.foo/1/', 'https://foo.foo/2/'])
            self.assertEqual(cache.cache.get(f'prefix:djangocms_oidc_provider:{provider.pk}'), '--PROGRESS--')
            frozen_datetime.tick(delta=datetime.timedelta(seconds=10))
            self.assertIsNone(cache.cache.get(f'prefix:djangocms_oidc_provider:{provider.pk}'))
        self.assertEqual(str(msg), '404 Client Error: None for url: https://foo.foo/register')

    @requests_mock.Mocker()
    def test_register_consumer_into_cache_expire_never(self, mock_req):
        mock_req.post("https://foo.foo/register", json={
            'client_secret_expires_at': 0,
            'client_secret': '5ed3a93b14cb5f1fdb97cb3dde1daddade443753eeb84432320b78a2',
            'client_id': '1d9G0Oid4E5V'
        })
        provider = OIDCProvider.objects.create(
            name="Provider", slug="provider", register_consumer=self.register_consumer)
        msg = provider.register_consumer_into_cache(['https://foo.foo/1/', 'https://foo.foo/2/'])
        self.assertIsNone(msg)
        data = cache.cache.get(f'prefix:djangocms_oidc_provider:{provider.pk}')
        self.assertEqual(data, {
            'client_id': '1d9G0Oid4E5V',
            'client_secret': '5ed3a93b14cb5f1fdb97cb3dde1daddade443753eeb84432320b78a2',
            'expires_at': 'never',
        })

    @freeze_time('2020-10-06 15:00:00')
    @requests_mock.Mocker()
    def test_register_consumer_into_cache(self, mock_req):
        mock_req.post("https://foo.foo/register", json={
            'client_id_issued_at': 1601989200,
            'response_types': ['code'],
            'request_object_signing_alg': 'HS256',
            'registration_client_uri': 'https://mojeid.regtest.nic.cz/oidc/registration/?client_id=1d9G0Oid4E5V',
            'application_type': 'web',
            'registration_access_token': 'zhbvda8JZgsamO8Lm0TgZ0UA50cLXrZm',
            'redirect_uris': ['http://localhost/oidc/callback/'],
            'client_secret_expires_at': 1602075600,
            'client_secret': '5ed3a93b14cb5f1fdb97cb3dde1daddade443753eeb84432320b78a2',
            'client_name': 'MojeID Test - Dynamic consumer',
            'client_id': '1d9G0Oid4E5V'
        })
        provider = OIDCProvider.objects.create(
            name="Provider", slug="provider", register_consumer=self.register_consumer)
        msg = provider.register_consumer_into_cache(['https://foo.foo/1/', 'https://foo.foo/2/'])
        self.assertIsNone(msg)
        data = cache.cache.get(f'prefix:djangocms_oidc_provider:{provider.pk}')
        self.assertEqual(data, {
            'client_id': '1d9G0Oid4E5V',
            'client_secret': '5ed3a93b14cb5f1fdb97cb3dde1daddade443753eeb84432320b78a2',
            'expires_at': datetime.datetime(2020, 10, 7, 13, 0, tzinfo=datetime.timezone.utc),
        })

    def test_get_registration_consumer_info_managed(self):
        provider = OIDCProvider.objects.create(name="Provider", slug="provider", client_id=42)
        data = provider.get_registration_consumer_info()
        self.assertEqual(data, {'client_id': 42, 'expires_at': None, 'consumer_type': 'MANAGED'})

    def test_get_registration_consumer_info_automatic(self):
        provider = OIDCProvider.objects.create(name="Provider", slug="provider")
        data = provider.get_registration_consumer_info()
        self.assertEqual(data, {'client_id': None, 'expires_at': None, 'consumer_type': 'AUTOMATIC'})

    def test_get_registration_consumer_info_automatic_from_cache(self):
        provider = OIDCProvider.objects.create(name="Provider", slug="provider")
        cache.cache.set(f'prefix:djangocms_oidc_provider:{provider.pk}', {
            'client_id': 42, 'expires_at': 'never'})
        data = provider.get_registration_consumer_info()
        self.assertEqual(data, {'client_id': 42, 'expires_at': 'never', 'consumer_type': 'AUTOMATIC'})


class TestValidateClaims(SimpleTestCase):

    def test_no_userinfo(self):
        validate_claims({})

    def test_no_dict_type(self):
        with self.assertRaisesMessage(ValidationError, "The value must be a dictionary type: {}"):
            validate_claims('')

    def test_userinfo_is_str(self):
        with self.assertRaisesMessage(
                ValidationError, 'The value "userinfo" must be a dictionary type: {"userinfo": ...}'):
            validate_claims({'userinfo': 'foo'})

    def test_userinfo_item_is_str(self):
        with self.assertRaisesMessage(
                ValidationError, 'The "name" must be a dictionary type: "name": {"essential": true},'):
            validate_claims({'userinfo': {'name': 'foo'}})

    def test_userinfo_essential_missing(self):
        with self.assertRaisesMessage(
                ValidationError, 'The "name" value must contain key "essential": "name": {"essential": true},'):
            validate_claims({'userinfo': {'name': {'value': 'foo'}}})

    def test_userinfo_essential_is_not_boolean(self):
        with self.assertRaisesMessage(
                ValidationError, 'The value of "essential" must be a boolean type": "name": {"essential": true},'):
            validate_claims({'userinfo': {'name': {'essential': 'foo'}}})

    def test_userinfo_with_claims(self):
        validate_claims({'userinfo': {'name': {'essential': True}}})


class TestOIDCHandoverData(SimpleTestCase):

    def test_provider(self):
        provider = OIDCProvider(name="Provider")
        consumer = OIDCHandoverData(provider=provider)
        self.assertEqual(str(consumer), "Provider")

    def test_no_provider(self):
        consumer = OIDCHandoverData()
        self.assertEqual(str(consumer), "[No provider yet]")

    def test_button(self):
        consumer = OIDCHandoverData(button_label="Foo")
        self.assertEqual(str(consumer), "Foo")


class TestOIDCShowAttribute(SimpleTestCase):

    def test(self):
        show_arrib = OIDCShowAttribute(verified_by="Provider")
        self.assertEqual(str(show_arrib), "Provider")


class TestOIDCDisplayDedicatedContent(TestCase):

    def test_none(self):
        model = OIDCDisplayDedicatedContent.objects.create()
        self.assertEqual(str(model), "?")

    def test_only_authenticated_user(self):
        model = OIDCDisplayDedicatedContent.objects.create(conditions='only_authenticated_user')
        self.assertEqual(str(model), "Only authenticated user")

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from djangocms_oidc import helpers
from djangocms_oidc.constants import DJANGOCMS_PLUGIN_SESSION_KEY, DJANGOCMS_USER_SESSION_KEY
from djangocms_oidc.models import OIDCHandoverData, OIDCIdentifier, OIDCProvider


class TestHelpers(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.provider = OIDCProvider.objects.create(
            name="Provider", slug="provider", client_id="example_id", client_secret="client_secret",
            token_endpoint="https://foo.foo/token", user_endpoint="https://foo.foo/user")
        cls.plugin = OIDCHandoverData.objects.create(provider=cls.provider)
        cls.user = get_user_model().objects.create(username="admin")

    def test_set_consumer(self):
        request = RequestFactory().request()
        request.session = {}
        helpers.set_consumer(request, self.plugin)
        self.assertEqual(request.session, {DJANGOCMS_PLUGIN_SESSION_KEY: ('handover', self.plugin.pk)})

    def test_get_consumer_none(self):
        request = RequestFactory().request()
        request.session = {}
        self.assertIsNone(helpers.get_consumer(request))

    def test_get_consumer_object_does_not_exists(self):
        request = RequestFactory().request()
        request.session = {DJANGOCMS_PLUGIN_SESSION_KEY: ('handover', 42)}
        self.assertIsNone(helpers.get_consumer(request))

    def test_get_consumer(self):
        request = RequestFactory().request()
        request.session = {DJANGOCMS_PLUGIN_SESSION_KEY: ('handover', self.plugin.pk)}
        plugin = helpers.get_consumer(request)
        self.assertEqual(self.plugin, plugin)

    def test_load_consumer_unknown_type(self):
        plugin = helpers.load_consumer('foo', self.plugin.pk)
        self.assertIsNone(plugin)

    def test_load_consumer_object_does_not_exists(self):
        plugin = helpers.load_consumer('handover', 42)
        self.assertIsNone(plugin)

    def test_load_consumer(self):
        plugin = helpers.load_consumer('handover', self.plugin.pk)
        self.assertEqual(self.plugin, plugin)

    def test_get_user_identifiers_formset_empty(self):
        formset = helpers.get_user_identifiers_formset(self.user)
        self.assertFalse(formset.is_bound)
        self.assertEqual(formset.get_queryset().count(), 0)

    def test_get_user_identifiers_formset(self):
        OIDCIdentifier.objects.create(user=self.user, provider=self.provider, uident="1234567890")
        formset = helpers.get_user_identifiers_formset(self.user)
        self.assertFalse(formset.is_bound)
        self.assertQuerysetEqual(formset.get_queryset().values_list('uident', flat=True), [
            '1234567890'], transform=str)

    def test_check_required_handovered(self):
        self.plugin.claims = {
            "userinfo": {
                "openid2_id": {"essential": True},
                "email": {"essential": True},
            }
        }
        user_info = {"openid2_id": "ID", "email": "mail@foo.foo", "name": "Name"}
        self.assertTrue(helpers.check_required_handovered(self.plugin, user_info))

    def test_check_required_handovered_failsed(self):
        self.plugin.claims = {
            "userinfo": {
                "openid2_id": {"essential": True},
                "email": {"essential": True},
            }
        }
        user_info = {"openid2_id": "ID", "name": "Name"}
        self.assertFalse(helpers.check_required_handovered(self.plugin, user_info))

    def test_get_verified_as_default(self):
        name = helpers.get_verified_as(None, None, "Default")
        self.assertEqual(name, "Default")

    def test_get_verified_as_empty_no_verified_by(self):
        user_info = {"name": "Arnold Rimmer", "given_name": "Dave", "family_name": "Lister"}
        name = helpers.get_verified_as("", user_info, "Default")
        self.assertEqual(name, "Default")

    def test_get_verified_as_name(self):
        verified_by = "name given_name+family_name email"
        user_info = {"name": "Arnold Rimmer", "given_name": "Dave", "family_name": "Lister"}
        name = helpers.get_verified_as(verified_by, user_info, "Default")
        self.assertEqual(name, "Arnold Rimmer")

    def test_get_verified_as_given_and_family_name(self):
        verified_by = "given_name+family_name name email"
        user_info = {"name": "Arnold Rimmer", "given_name": "Dave", "family_name": "Lister"}
        name = helpers.get_verified_as(verified_by, user_info, "Default")
        self.assertEqual(name, "Dave Lister")

    def test_get_verified_as_email(self):
        verified_by = "given_name+family_name name email"
        user_info = {"email": "mail@foo.foo"}
        name = helpers.get_verified_as(verified_by, user_info, "Default")
        self.assertEqual(name, "mail@foo.foo")

    def test_get_user_info_is_none(self):
        request = RequestFactory().request()
        request.session = {}
        self.assertIsNone(helpers.get_user_info(request))

    def test_get_user_info(self):
        request = RequestFactory().request()
        request.session = {DJANGOCMS_USER_SESSION_KEY: 'ok'}
        self.assertEqual(helpers.get_user_info(request), 'ok')

    def test_clear_user_info_is_empty(self):
        request = RequestFactory().request()
        request.session = {}
        helpers.clear_user_info(request)
        self.assertEqual(request.session, {})

    def test_clear_user_info(self):
        request = RequestFactory().request()
        request.session = {DJANGOCMS_USER_SESSION_KEY: 'ok'}
        helpers.clear_user_info(request)
        self.assertEqual(request.session, {})

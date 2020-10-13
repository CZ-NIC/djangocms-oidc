from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase, override_settings
from django.test.client import RequestFactory

from djangocms_oidc import utils


class TestUtils(SimpleTestCase):

    @override_settings(EXAMPLE_VARIABLE='example_value')
    def test_get_settings(self):
        value = utils.get_settings('EXAMPLE_VARIABLE')
        self.assertEqual(value, 'example_value')

    @override_settings(CMS_CACHE_PREFIX='prefix:')
    def test_get_cache_key(self):
        value = utils.get_cache_key("key")
        self.assertEqual(value, 'prefix:key')

    def test_only_user_is_staff_no_user(self):
        request = RequestFactory().request()
        context = {'request': request}
        self.assertFalse(utils.only_user_is_staff(context, None, None, None))

    def test_only_user_is_staff_user_is_not_staff(self):
        request = RequestFactory().request()
        request.user = get_user_model()()
        context = {'request': request}
        self.assertFalse(utils.only_user_is_staff(context, None, None, None))

    def test_only_user_is_staff(self):
        request = RequestFactory().request()
        request.user = get_user_model()(is_staff=True)
        context = {'request': request}
        self.assertTrue(utils.only_user_is_staff(context, None, None, None))

    def test_only_authenticated_user_no_user(self):
        request = RequestFactory().request()
        context = {'request': request}
        self.assertFalse(utils.only_authenticated_user(context, None, None, None))

    def test_only_authenticated_user_is_not_authenticated(self):
        request = RequestFactory().request()
        request.user = AnonymousUser()
        context = {'request': request}
        self.assertFalse(utils.only_authenticated_user(context, None, None, None))

    def test_only_authenticated_user(self):
        request = RequestFactory().request()
        request.user = get_user_model()()
        context = {'request': request}
        self.assertTrue(utils.only_authenticated_user(context, None, None, None))

    def test_email_verified_user_info_is_none(self):
        context = {}
        self.assertFalse(utils.email_verified(context, None, None, None))
        self.assertEqual(context, {})

    def test_email_verified(self):
        context = {}
        user_info = {
            'email': 'foo@foo.foo',
            'email_verified': True,
        }
        self.assertTrue(utils.email_verified(context, None, None, user_info))
        self.assertEqual(context, {})

    def test_email_verified_email_missing(self):
        context = {}
        user_info = {
            'email_verified': True,
        }
        self.assertFalse(utils.email_verified(context, None, None, user_info))
        self.assertEqual(context, {
            'dedicated_content': '''<ul class='messagelist'><li class='error'>Email missing.</li></ul>'''
        })

    def test_email_verified_email_verified_missing(self):
        context = {}
        user_info = {
            'email': 'foo@foo.foo',
        }
        self.assertFalse(utils.email_verified(context, None, None, user_info))
        self.assertEqual(context, {
            'dedicated_content': '''<ul class='messagelist'><li class='error'>Email is not verified.</li></ul>'''
        })

    def test_email_verified_all_missing(self):
        context = {}
        user_info = {}
        self.assertFalse(utils.email_verified(context, None, None, user_info))
        self.assertEqual(context, {
            'dedicated_content': '''<ul class='messagelist'><li class='error'>Email missing. '''
                                 '''Email is not verified.</li></ul>'''
        })

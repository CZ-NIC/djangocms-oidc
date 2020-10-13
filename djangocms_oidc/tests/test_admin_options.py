from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import TestCase

from djangocms_oidc.admin.options import OIDCIdentifierAdmin
from djangocms_oidc.models import OIDCIdentifier


class TestAdminOptions(TestCase):

    def test_user_email(self):
        admin = OIDCIdentifierAdmin(admin_site=site, model=OIDCIdentifier)
        user = get_user_model()(email="email@foo.foo")
        obj = OIDCIdentifier(user=user)
        self.assertEqual(admin.user_email(obj), "email@foo.foo")

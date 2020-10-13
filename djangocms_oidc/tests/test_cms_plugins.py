import datetime

from cms.api import add_plugin
from cms.models import Placeholder
from cms.models.pluginmodel import CMSPlugin
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from cms.plugin_rendering import ContentRenderer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core import cache
from django.test import RequestFactory, TestCase, override_settings

from djangocms_oidc.cms_plugins import (
    OIDCDisplayDedicatedContentPlugin,
    OIDCHandoverDataPlugin,
    OIDCListIdentifiersPlugin,
    OIDCLoginPlugin,
    OIDCShowAttributeCountryPlugin,
    OIDCShowAttributePlugin,
)
from djangocms_oidc.constants import DJNAGOCMS_USER_SESSION_KEY
from djangocms_oidc.models import (
    OIDCDisplayDedicatedContent,
    OIDCHandoverData,
    OIDCIdentifier,
    OIDCLogin,
    OIDCProvider,
    OIDCShowAttribute,
)


class CreateInstancesMixin:

    def _create_model(self, plugin_class, **kwargs):
        placeholder = Placeholder.objects.create(slot='test')
        model_instance = add_plugin(
            placeholder,
            plugin_class,
            'en',
            **kwargs
        )
        return model_instance

    def _create_request(self):
        request = RequestFactory().request()
        request.session = {}
        return request


class CreateProviderTestCase(CreateInstancesMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.provider = OIDCProvider.objects.create(
            name="Provider", slug="provider", client_id="example_id", client_secret="client_secret",
            token_endpoint="https://foo.foo/token", user_endpoint="https://foo.foo/user")


class TestOIDCHandoverDataPlugin(CreateProviderTestCase):

    def test_get_verified_as(self):
        user_info = {}
        model_instance = self._create_model(OIDCHandoverDataPlugin, provider=self.provider)
        plugin_instance = model_instance.get_plugin_class_instance()
        name = plugin_instance.get_verified_as(model_instance, user_info)
        self.assertEqual(name, 'User')

    def test_get_verified_as_email(self):
        user_info = {'email': 'mail@foo.foo', 'name': 'Tester'}
        model_instance = self._create_model(OIDCHandoverDataPlugin, provider=self.provider, verified_by="email")
        plugin_instance = model_instance.get_plugin_class_instance()
        name = plugin_instance.get_verified_as(model_instance, user_info)
        self.assertEqual(name, 'mail@foo.foo')

    def test_plugin_context(self):
        model_instance = self._create_model(OIDCHandoverDataPlugin, provider=self.provider)
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], OIDCHandoverData)
        self.assertEqual(context['registration_consumer_info'], {
            'client_id': 'example_id', 'expires_at': None, 'consumer_type': 'MANAGED'})

    def test_plugin_context_with_user_info(self):
        model_instance = self._create_model(OIDCHandoverDataPlugin, provider=self.provider, verified_by="name")
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'email': 'mail@foo.foo', 'name': 'Tester'}
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], OIDCHandoverData)
        self.assertEqual(context['registration_consumer_info'], {
            'client_id': 'example_id', 'expires_at': None, 'consumer_type': 'MANAGED'})
        self.assertEqual(context['djangocms_oidc_user_info'], {'email': 'mail@foo.foo', 'name': 'Tester'})
        self.assertTrue(context['all_required_handovered'])
        self.assertEqual(context['djangocms_oidc_verified_as'], 'Tester')

    def test_plugin_html(self):
        model_instance = self._create_model(OIDCHandoverDataPlugin, provider=self.provider)
        request = self._create_request()
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, """
            <span class="djangocms-oidc">
                <a href="/oidc-sign-up/handover-{model_id}/" class="djangocms-oidc-signup provider"
                        data-consumer_type="MANAGED"
                        data-client_id="example_id"
                        data-expires_at="">
                    Data handover from Provider
                </a>
            </span>""".format(model_id=model_instance.pk))

    def test_plugin_html_with_user_info(self):
        model_instance = self._create_model(OIDCHandoverDataPlugin, provider=self.provider, verified_by="name")
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'email': 'mail@foo.foo', 'name': 'Tester'}
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, """
            <span class="djangocms-oidc">
                You are verified as <span class="djangocms-oidc-verified_as">Tester</span>.
                <a href="/oidc-dismiss/" class="djangocms-oidc-dismiss provider" title="Dismiss data from Provider.">
                    Dismiss
                </a>
                <a href="/oidc-sign-up/handover-{model_id}/" class="djangocms-oidc-signup update-data provider"
                        data-consumer_type="MANAGED"
                        data-client_id="example_id"
                        data-expires_at="">
                    Update data
                </a>
            </span>""".format(model_id=model_instance.pk))

    def test_plugin_html_with_user_info_and_urls_all_required_handovered(self):
        model_instance = self._create_model(OIDCHandoverDataPlugin, provider=self.provider, verified_by="name")
        model_instance.provider.account_url = "https://provider.foo/account"
        model_instance.provider.logout_url = "https://provider.foo/logout"
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'email': 'mail@foo.foo', 'name': 'Tester'}
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, """
            <span class="djangocms-oidc">
                    You are verified as
                    <span class="djangocms-oidc-verified_as">
                        <a href="https://provider.foo/account" class="djangocms-oidc-account provider">Tester</a>
                    </span>.
                    <a href="/oidc-dismiss/" class="djangocms-oidc-dismiss provider"
                            title="Dismiss data from Provider.">
                        Dismiss
                    </a>
                    <a href="/oidc-sign-up/handover-{model_id}/" class="djangocms-oidc-signup update-data provider"
                            data-consumer_type="MANAGED"
                            data-client_id="example_id"
                            data-expires_at="">
                        Update data
                    </a>
                    <div>
                        You can also log out of provider
                        <a href="https://provider.foo/logout" class="djangocms-oidc-logout provider">Provider</a>
                        if you wish.
                    </div>
            </span>""".format(model_id=model_instance.pk))

    def test_plugin_html_with_user_info_and_urls(self):
        claims = {
            'userinfo': {"email": {"essential": True}},
        }
        model_instance = self._create_model(
            OIDCHandoverDataPlugin, provider=self.provider, verified_by="name", claims=claims)
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'name': 'Tester'}
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, """
            <span class="djangocms-oidc">
                You are verified as <span class="djangocms-oidc-verified_as">Tester</span>.
                <a href="/oidc-dismiss/" class="djangocms-oidc-dismiss provider" title="Dismiss data from Provider.">
                    Dismiss
                </a>
                <span class="all-required-not-handovered">
                    <span>Not all required data has been handovered.</span>
                    <a href="/oidc-sign-up/handover-{model_id}consent/"
                            class="djangocms-oidc-signup remaining-data provider"
                            data-consumer_type="MANAGED"
                            data-client_id="example_id"
                            data-expires_at="">
                        Handover the remaining data
                    </a>
                </span>
            </span>""".format(model_id=model_instance.pk))

    @override_settings(CMS_CACHE_PREFIX='prefix:')
    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_plugin_html_with_automatic_registration(self):
        provider = OIDCProvider.objects.create(name="Autoregistraion Provider", slug="autoreg-provider")
        placeholder = Placeholder.objects.create(slot='test')
        model_instance = add_plugin(placeholder, OIDCHandoverDataPlugin, 'en', provider=provider)
        request = self._create_request()
        cache.cache.set('prefix:djangocms_oidc_provider:{}'.format(provider.pk), {
            'client_id': 42,
            'expires_at': datetime.datetime(2020, 10, 7, 14, 42, 21)
        })
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, """
            <span class="djangocms-oidc">
                <a href="/oidc-sign-up/handover-{model_id}/" class="djangocms-oidc-signup autoreg-provider"
                        data-consumer_type="AUTOMATIC"
                        data-client_id="42"
                        data-expires_at="2020-10-07T14:42:21">
                    Data handover from Autoregistraion Provider
                </a>
            </span>""".format(model_id=model_instance.pk))


class TestOIDCLoginPluginPlugin(CreateProviderTestCase):

    def test_plugin_context(self):
        model_instance = self._create_model(OIDCLoginPlugin, provider=self.provider)
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], OIDCLogin)
        self.assertEqual(context['registration_consumer_info'], {
            'client_id': 'example_id', 'expires_at': None, 'consumer_type': 'MANAGED'})

    def test_plugin_html(self):
        model_instance = self._create_model(OIDCLoginPlugin, provider=self.provider)
        request = self._create_request()
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, """
            <span class="djangocms-oidc">
                <a href="/oidc-sign-up/login-{model_id}/" class="djangocms-oidc-signup provider"
                        data-consumer_type="MANAGED"
                        data-client_id="example_id"
                        data-expires_at="">
                    Login by Provider
                </a>
            </span>""".format(model_id=model_instance.pk))

    def test_plugin_html_with_user_info(self):
        model_instance = self._create_model(OIDCLoginPlugin, provider=self.provider, verified_by="name")
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'email': 'mail@foo.foo', 'name': 'Tester'}
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, """
            <span class="djangocms-oidc">
                You are verified as <span class="djangocms-oidc-verified_as">Tester</span>.
                <a href="/oidc-dismiss/" class="djangocms-oidc-dismiss provider" title="Dismiss data from Provider.">
                    Dismiss
                </a>
                <a href="/oidc-sign-up/login-{model_id}/" class="djangocms-oidc-signup update-data provider"
                        data-consumer_type="MANAGED"
                        data-client_id="example_id"
                        data-expires_at="">
                    Update data
                </a>
                <a href="/oidc-sign-up/login-{model_id}/" class="djangocms-oidc-signup provider"
                        data-consumer_type="MANAGED"
                        data-client_id="example_id"
                        data-expires_at="">
                    Login by Provider
                </a>
            </span>""".format(model_id=model_instance.pk))

    def test_plugin_html_with_user_info_and_urls_all_required_handovered(self):
        model_instance = self._create_model(OIDCLoginPlugin, provider=self.provider, verified_by="name")
        model_instance.provider.account_url = "https://provider.foo/account"
        model_instance.provider.logout_url = "https://provider.foo/logout"
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'name': 'Tester'}
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, """
            <span class="djangocms-oidc">
                You are verified as
                <span class="djangocms-oidc-verified_as">
                    <a href="https://provider.foo/account" class="djangocms-oidc-account provider">Tester</a>
                </span>.
                <a href="/oidc-dismiss/" class="djangocms-oidc-dismiss provider" title="Dismiss data from Provider.">
                    Dismiss
                </a>
                <a href="/oidc-sign-up/login-{model_id}/" class="djangocms-oidc-signup update-data provider"
                        data-consumer_type="MANAGED"
                        data-client_id="example_id"
                        data-expires_at="">
                    Update data
                </a>
                <div>
                    You can also log out of provider
                    <a href="https://provider.foo/logout" class="djangocms-oidc-logout provider">Provider</a>
                    if you wish.
                </div>
                <a href="/oidc-sign-up/login-{model_id}/" class="djangocms-oidc-signup provider"
                        data-consumer_type="MANAGED"
                        data-client_id="example_id"
                        data-expires_at="">
                    Login by Provider
                </a>
            </span>""".format(model_id=model_instance.pk))

    def test_plugin_html_with_user_info_and_urls(self):
        claims = {
            'userinfo': {"email": {"essential": True}},
        }
        model_instance = self._create_model(OIDCLoginPlugin, provider=self.provider, verified_by="name", claims=claims)
        model_instance.provider.account_url = "https://provider.foo/account"
        model_instance.provider.logout_url = "https://provider.foo/logout"
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'name': 'Tester'}
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, """
            <span class="djangocms-oidc">
                You are verified as
                <span class="djangocms-oidc-verified_as">
                    <a href="https://provider.foo/account" class="djangocms-oidc-account provider">Tester</a>
                </span>.
                <a href="/oidc-dismiss/" class="djangocms-oidc-dismiss provider" title="Dismiss data from Provider.">
                    Dismiss
                </a>
                <span class="all-required-not-handovered">
                    <span>Not all required data has been handovered.</span>
                    <a href="/oidc-sign-up/login-{model_id}consent/"
                            class="djangocms-oidc-signup remaining-data provider">
                        Handover the remaining data
                    </a>
                </span>
                <div>
                    You can also log out of provider
                    <a href="https://provider.foo/logout" class="djangocms-oidc-logout provider">Provider</a>
                    if you wish.
                </div>
                <a href="/oidc-sign-up/login-{model_id}/" class="djangocms-oidc-signup provider"
                        data-consumer_type="MANAGED"
                        data-client_id="example_id"
                        data-expires_at="">
                    Login by Provider
                </a>
            </span>""".format(model_id=model_instance.pk))

    def test_plugin_html_no_new_user(self):
        model_instance = self._create_model(OIDCLoginPlugin, provider=self.provider, no_new_user=True)
        request = self._create_request()
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, """
            <span class="djangocms-oidc">
                <span class="pair-info">
                    <a href="/login/" class="djangocms-oidc-login"
                        title="To pair your account with an identity provider, sign in first.">
                        Login
                    </a>
                </span>
                <a href="/oidc-sign-up/login-{model_id}/" class="djangocms-oidc-signup provider login-required"
                        data-consumer_type="MANAGED"
                        data-client_id="example_id"
                        data-expires_at="">
                    Pair by Provider
                </a>
            </span>""".format(model_id=model_instance.pk))

    def test_plugin_html_user_is_authenticated(self):
        model_instance = self._create_model(OIDCLoginPlugin, provider=self.provider)
        request = self._create_request()
        request.user = get_user_model()()
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request, 'user': request.user})
        self.assertHTMLEqual(html, """
            <span class="djangocms-oidc">
                <a href="/oidc-sign-up/login-{model_id}/"
                        class="djangocms-oidc-signup provider"
                        title="Pair my account with an identity provider">
                    Pair by Provider
                </a>
                <a href="/oidc-logout/" class="logout-from-editation">Logout</a>
            </span>""".format(model_id=model_instance.pk))


@plugin_pool.register_plugin
class TestContentPlugin(CMSPluginBase):
    model = CMSPlugin
    name = "Test Content Plugin."
    render_template = "test_content_plugin.html"


class TestOIDCDisplayDedicatedContentPlugin(CreateInstancesMixin, TestCase):

    def _create_plugin_content(self, parent_instance, **attrs):
        instance = CMSPlugin(
            parent=parent_instance,
            placeholder=parent_instance.placeholder,
            language=parent_instance.language,
            position=CMSPlugin.objects.filter(parent=parent_instance).count(),
            plugin_type=TestContentPlugin.__name__,
            **attrs
        )
        instance.save()
        if parent_instance.child_plugin_instances is None:
            parent_instance.child_plugin_instances = [instance]
        else:
            parent_instance.child_plugin_instances.append(instance)
        return instance

    def test_plugin_context_conditions_empty(self):
        model_instance = self._create_model(OIDCDisplayDedicatedContentPlugin)
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], OIDCDisplayDedicatedContent)
        self.assertFalse(context['content_permitted_to_user'])

    def test_plugin_context_no_permissions(self):
        model_instance = self._create_model(OIDCDisplayDedicatedContentPlugin, conditions='only_authenticated_user')
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        request.user = get_user_model()()
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], OIDCDisplayDedicatedContent)
        self.assertTrue(context['content_permitted_to_user'])

    def test_plugin_html_conditions_email_verified(self):
        model_instance = self._create_model(OIDCDisplayDedicatedContentPlugin, conditions='email_verified')
        self._create_plugin_content(model_instance)
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'email': 'mail@foo.foo', 'email_verified': True}
        request.current_page = None
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, "<p>Test Content Plugin.</p>")

    def test_plugin_html_conditions_uset_authenticated(self):
        model_instance = self._create_model(OIDCDisplayDedicatedContentPlugin)
        self._create_plugin_content(model_instance)
        request = self._create_request()
        request.current_page = None
        request.user = get_user_model()()
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request, 'user': request.user})
        self.assertHTMLEqual(html, "<p>Test Content Plugin.</p>")

    def test_plugin_html_conditions_email_not_verified(self):
        model_instance = self._create_model(OIDCDisplayDedicatedContentPlugin, conditions='email_verified')
        self._create_plugin_content(model_instance)
        self._create_plugin_content(model_instance)
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'email': 'mail@foo.foo'}
        request.current_page = None
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, "<ul class='messagelist'><li class='error'>Email is not verified.</li></ul>")


class TestOIDCListIdentifiersPlugin(CreateProviderTestCase):

    def test_plugin_context_user_is_not_authenticated(self):
        model_instance = self._create_model(OIDCListIdentifiersPlugin)
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        request.user = AnonymousUser()
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], CMSPlugin)
        self.assertIsNone(context.get('user_has_identifiers'))

    def test_plugin_context_user_is_authenticated(self):
        model_instance = self._create_model(OIDCListIdentifiersPlugin)
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        request.user = get_user_model()()
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], CMSPlugin)
        self.assertFalse(context['user_has_identifiers'])
        self.assertQuerysetEqual(context['formset'].get_queryset().values_list('uident', flat=True), [])

    def test_plugin_context_user_with_identifier(self):
        model_instance = self._create_model(OIDCListIdentifiersPlugin)
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        User = get_user_model()
        request.user = User.objects.create(username="admin")
        OIDCIdentifier.objects.create(user=request.user, provider=self.provider, uident="1234567890")
        another_user = User.objects.create(username="other")
        OIDCIdentifier.objects.create(user=another_user, provider=self.provider, uident="42")
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], CMSPlugin)
        self.assertTrue(context['user_has_identifiers'])
        self.assertQuerysetEqual(context['formset'].get_queryset().values_list('uident', flat=True), [
            '1234567890'], transform=str)

    def test_plugin_html(self):
        model_instance = self._create_model(OIDCListIdentifiersPlugin)
        request = self._create_request()
        request.user = get_user_model()()
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request, 'user': request.user})
        self.assertHTMLEqual(html, """
            <p class="djangocms-oidc-no-linked-identifiers">
                You have no identifiers associated with the provider.
            </p>""")

    def test_plugin_html_with_identifiers(self):
        model_instance = self._create_model(OIDCListIdentifiersPlugin)
        request = self._create_request()
        User = get_user_model()
        request.user = User.objects.create(username="admin")
        ident = OIDCIdentifier.objects.create(user=request.user, provider=self.provider, uident="1234567890")
        another_user = User.objects.create(username="other")
        OIDCIdentifier.objects.create(user=another_user, provider=self.provider, uident="42")
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request, 'user': request.user})
        self.assertHTMLEqual(html, """
            <form class="djangocms-oidc-delete-identifiers" method="post" action="/oidc-delete-identifiers/">
                <input type="hidden" name="form-TOTAL_FORMS" value="1" id="id_form-TOTAL_FORMS">
                <input type="hidden" name="form-INITIAL_FORMS" value="1" id="id_form-INITIAL_FORMS">
                <input type="hidden" name="form-MIN_NUM_FORMS" value="0" id="id_form-MIN_NUM_FORMS">
                <input type="hidden" name="form-MAX_NUM_FORMS" value="1000" id="id_form-MAX_NUM_FORMS">
                <ul class="user-identifiers">
                    <li>
                        <input type="hidden" name="form-0-cmsplugin_ptr" value="{id}" id="id_form-0-cmsplugin_ptr">
                        <input type="checkbox" name="form-0-DELETE" id="id_form-0-DELETE">
                        <span class="user-identity">1234567890</span>
                    </li>
                </ul>
                <input type="submit" name="djangocms_oidc_delete_identifier" value="Delete selected">
            </form>""".format(id=ident.pk))


class TestOIDCShowAttributePlugin(CreateInstancesMixin, TestCase):

    def test_plugin_context(self):
        model_instance = self._create_model(OIDCShowAttributePlugin)
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], OIDCShowAttribute)
        self.assertIsNone(context['djangocms_oidc_verified_as'])

    def test_plugin_context_with_default(self):
        model_instance = self._create_model(OIDCShowAttributePlugin, default_value="Default")
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], OIDCShowAttribute)
        self.assertEqual(context['djangocms_oidc_verified_as'], 'Default')

    def test_plugin_context_from_session(self):
        model_instance = self._create_model(OIDCShowAttributePlugin, default_value="Default", verified_by="email")
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'email': 'mail@foo.foo', 'name': 'Tester'}
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], OIDCShowAttribute)
        self.assertEqual(context['djangocms_oidc_verified_as'], 'mail@foo.foo')

    def test_plugin_html(self):
        model_instance = self._create_model(OIDCShowAttributePlugin)
        request = self._create_request()
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, "<span></span>")

    def test_plugin_html_with_default(self):
        model_instance = self._create_model(OIDCShowAttributePlugin, default_value="Default")
        request = self._create_request()
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, "<span>Default</span>")

    def test_plugin_html_from_session(self):
        model_instance = self._create_model(OIDCShowAttributePlugin, default_value="Default", verified_by="email")
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'email': 'mail@foo.foo', 'name': 'Tester'}
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, "<span>mail@foo.foo</span>")


class TestOIDCShowAttributeCountryPlugin(CreateInstancesMixin, TestCase):

    def test_plugin_context(self):
        model_instance = self._create_model(OIDCShowAttributeCountryPlugin)
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], OIDCShowAttribute)
        self.assertIsNone(context['djangocms_oidc_verified_as'])

    def test_plugin_context_from_session(self):
        model_instance = self._create_model(OIDCShowAttributeCountryPlugin, verified_by="country")
        plugin_instance = model_instance.get_plugin_class_instance()
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'country': 'CZ', 'name': 'Tester'}
        context = plugin_instance.render({'request': request}, model_instance, None)
        self.assertIsInstance(context['instance'], OIDCShowAttribute)
        self.assertEqual(context['djangocms_oidc_verified_as'], 'CZ')

    def test_plugin_html(self):
        model_instance = self._create_model(OIDCShowAttributeCountryPlugin)
        request = self._create_request()
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertEqual(html.strip(), "")

    def test_plugin_html_from_session(self):
        model_instance = self._create_model(OIDCShowAttributeCountryPlugin, verified_by="country")
        request = self._create_request()
        request.session[DJNAGOCMS_USER_SESSION_KEY] = {'country': 'CZ', 'name': 'Tester'}
        renderer = ContentRenderer(request=RequestFactory())
        html = renderer.render_plugin(model_instance, {'request': request})
        self.assertHTMLEqual(html, "<span>Czechia</span>")

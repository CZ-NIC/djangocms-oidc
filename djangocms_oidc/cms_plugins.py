from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from django.utils.translation import ugettext_lazy as _

from .constants import DJNAGOCMS_USER_SESSION_KEY
from .forms import OIDCDataForm
from .helpers import check_required_handovered, get_user_identifiers_formset, get_verified_as
from .models import (
    OIDCDisplayDedicatedContent,
    OIDCHandoverData,
    OIDCIdentifier,
    OIDCLogin,
    OIDCShowAttribute,
    get_display_content_settings,
)


class OIDCConsumerBase(CMSPluginBase):

    module = _('OpenID Connect')
    form = OIDCDataForm
    change_form_template = "djangocms_oidc/change_form/consumer.html"
    text_enabled = True
    cache = False

    def get_verified_as(self, instance, user_info):
        default = _("User")
        if instance.verified_by is None:
            return user_info.get('email', default)
        return get_verified_as(instance.verified_by, user_info, default)

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        user_info = context['request'].session.get(DJNAGOCMS_USER_SESSION_KEY)
        if user_info is not None:
            context['djangocms_oidc_user_info'] = user_info
            context['all_required_handovered'] = check_required_handovered(instance, user_info)
            context['djangocms_oidc_verified_as'] = self.get_verified_as(instance, user_info)
        context['registration_consumer_info'] = instance.provider.get_registration_consumer_info()
        return context


@plugin_pool.register_plugin
class OIDCHandoverDataPlugin(OIDCConsumerBase):
    name = _('OIDC Handover data')
    model = OIDCHandoverData
    render_template = "djangocms_oidc/handover_data.html"


@plugin_pool.register_plugin
class OIDCLoginPlugin(OIDCConsumerBase):
    name = _('OIDC Login')
    model = OIDCLogin
    render_template = "djangocms_oidc/login.html"


@plugin_pool.register_plugin
class OIDCListIdentifiersPlugin(CMSPluginBase):
    module = _('OpenID Connect')
    name = _('OIDC List identifiers')
    render_template = "djangocms_oidc/list_identifiers.html"
    change_form_template = "djangocms_oidc/change_form/list_identifiers.html"

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        if context['request'].user.is_authenticated:
            context['formset'] = get_user_identifiers_formset(context['request'].user)
            context['user_has_identifiers'] = OIDCIdentifier.objects.filter(user=context['request'].user).exists()
        return context


@plugin_pool.register_plugin
class OIDCDisplayDedicatedContentPlugin(CMSPluginBase):
    module = _('OpenID Connect')
    name = _('OIDC Display dedicated content')
    model = OIDCDisplayDedicatedContent
    render_template = "djangocms_oidc/display_dedicated_content.html"
    change_form_template = 'djangocms_oidc/change_form/display_dedicated_content.html'
    cache = False
    allow_children = True

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        user_info = context['request'].session.get(DJNAGOCMS_USER_SESSION_KEY)
        if instance.conditions is None:
            context['content_permitted_to_user'] = user_info is not None
        else:
            for code, dummy, fnc in get_display_content_settings():
                if code == instance.conditions:
                    context['content_permitted_to_user'] = fnc(context, instance, placeholder, user_info)
        return context


@plugin_pool.register_plugin
class OIDCShowAttributePlugin(CMSPluginBase):
    module = _('OpenID Connect')
    name = _('OIDC Show attribute')
    model = OIDCShowAttribute
    render_template = "djangocms_oidc/show_attribute.html"
    cache = False

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        user_info = context['request'].session.get(DJNAGOCMS_USER_SESSION_KEY)
        if user_info is not None:
            context['djangocms_oidc_verified_as'] = get_verified_as(
                instance.verified_by, user_info, instance.default_value)
        else:
            context['djangocms_oidc_verified_as'] = instance.default_value
        return context


@plugin_pool.register_plugin
class OIDCShowAttributeCountryPlugin(OIDCShowAttributePlugin):
    name = _('OIDC Show attribute Country')
    render_template = "djangocms_oidc/show_attribute_country.html"

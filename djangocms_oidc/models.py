import datetime
import logging

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from requests.exceptions import RequestException
from multiselectfield import MultiSelectField

import jsonfield
from cms.models.fields import PageField
from cms.models.pluginmodel import CMSPlugin

from .utils import DEFAULT_DISPLAY_CONTENT, get_cache_key, get_settings

HANDOVER_DATA = 'handover'
LOGIN_USER = 'login'

logger = logging.getLogger("djangocms_oidc")


class ConsumerRegistrationExpired(Exception):
    """Consumer registration expired."""


class OIDCRegisterConsumer(CMSPlugin):

    name = models.CharField(
        verbose_name=_('Name'), max_length=255, unique=True, default='Default',
        help_text=_("Registration name"))
    register_url = models.URLField(
        verbose_name=_('Register consumer URL'),
        help_text=_("Register consumer automaticaly, when it is not. (Client ID and secret missing)."))
    # TODO: More parameters:
    # application_type" "web"
    # redirect_uris: (given from mozilla-oidc urls)
    # request_object_signing_alg: OIDC_RP_SIGN_ALGO (HS256)
    # token_endpoint_auth_method: "client_secret_post"
    # response_types: ["code"]
    # client_name: (same as provider name)
    # logo_uri:

    def __str__(self):
        return self.name

    def get_payload(self, name, redirect_uris):
        return {
            "application_type": "web",
            "id_token_signed_response_alg": get_settings('OIDC_RP_SIGN_ALGO', 'HS256'),
            "redirect_uris": redirect_uris,
            "token_endpoint_auth_method": "client_secret_post",
            "response_types": ["code"],
            "client_name": name,
        }

    def make_registeration(self, name, redirect_uris):
        response = requests.post(self.register_url, data=self.get_payload(name, redirect_uris))
        response.raise_for_status()
        return response.json()
        # return response.json(): {
        #     'client_id_issued_at': 1598961156,
        #     'response_types': ['code'],
        #     'request_object_signing_alg': 'HS256',
        #     'registration_client_uri': 'https://mojeid.regtest.nic.cz/oidc/registration/?client_id=1d9G0Oid4E5V',
        #     'application_type': 'web',
        #     'registration_access_token': 'zhbvda8JZgsamO8Lm0TgZ0UA50cLXrZm',
        #     'redirect_uris': ['http://localhost:8180/oidc/callback/'],
        #     'client_secret_expires_at': 1599047556,
        #     'client_secret': '5ed3a93b14cb5f1fdb97cb3dde1daddade443753eeb84432320b78a2',
        #     'client_name': 'MojeID Test - Dynamic consumer',
        #     'client_id': '1d9G0Oid4E5V'
        # }


class OIDCProvider(CMSPlugin):

    name = models.CharField(verbose_name=_('Name'), max_length=255, unique=True, help_text=_("Provider name"))
    slug = models.SlugField(verbose_name=_('Code'),
                            help_text=_("Used, for example, as a css class for a button or link."))
    client_id = models.CharField(
        verbose_name=_('Client ID'), max_length=255, null=True, blank=True,
        help_text=_('The value is required if "Register consumer" is not set.'))
    client_secret = models.CharField(
        verbose_name=_('Client secret'), max_length=255, null=True, blank=True,
        help_text=_('The value is required if "Register consumer" is not set.'))
    register_consumer = models.ForeignKey(
        OIDCRegisterConsumer, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_('Register consumer'),
        help_text=_("Register consumer on the provider, when Client ID and secret are not set."))
    authorization_endpoint = models.URLField(verbose_name=_('Authorization endpoint'))
    token_endpoint = models.URLField(verbose_name=_('Token endpoint'))
    user_endpoint = models.URLField(verbose_name=_('User endpoint'))
    account_url = models.URLField(verbose_name=_('Account URL'), null=True, blank=True)
    logout_url = models.URLField(verbose_name=_('Logout URL'), null=True, blank=True)

    progress_code = "--PROGRESS--"

    def __str__(self):
        return self.name

    def _get_cached(self, key):
        data = cache.get(self.get_cache_key())
        if data is None:
            raise ConsumerRegistrationExpired()
        return data[key]

    def get_client_id(self):
        if self.client_id:
            return self.client_id
        return self._get_cached('client_id')

    def get_client_secret(self):
        if self.client_secret:
            return self.client_secret
        return self._get_cached('client_secret')

    def needs_register(self):
        if self.client_id:
            return False
        return cache.get(self.get_cache_key()) is None

    def get_cache_key(self):
        return get_cache_key("djangocms_oidc_provider:{}".format(self.pk))

    def registration_in_progress(self):
        return cache.get(self.get_cache_key()) == self.progress_code

    def register_consumer_into_cache(self, redirect_uris):
        logger.info("Register consumer at {}".format(self.register_consumer.register_url))
        key = self.get_cache_key()
        cache.set(key, self.progress_code, 10)  # Assign the key for 10 seconds.
        try:
            data = self.register_consumer.make_registeration(self.name, redirect_uris)
        except RequestException as msg:
            logger.error(msg)
            return msg
        logger.info(data)
        if data['client_secret_expires_at'] == 0:
            expires_at = "never"
            duration = None
        else:
            expires_at = datetime.datetime.fromtimestamp(data['client_secret_expires_at'])
            expires_at = timezone.make_aware(expires_at, timezone.utc)
            duration = expires_at.timestamp() - timezone.now().timestamp()
        logger.info("Expires at {}".format(expires_at))
        content = {
            'client_id': data['client_id'],
            'client_secret': data['client_secret'],
            'expires_at': expires_at,
        }
        cache.set(key, content, duration)
        logger.debug("Store into cache: {} for {} sec.".format(key, duration))
        return None

    def get_registratin_consumer_info(self):
        data = {
            'client_id': None,
            'expires_at': None,
        }
        if self.client_id:
            data['consumer_type'] = 'MANAGED'
            data['client_id'] = self.client_id
        else:
            data['consumer_type'] = 'AUTOMATIC'
            info = cache.get(self.get_cache_key())
            if info is not None:
                data['client_id'] = info.get('client_id')
                data['expires_at'] = info.get('expires_at')
        return data


def validate_claims(value):
    """Validate Claims."""
    if not isinstance(value, dict):
        raise ValidationError(_("The value must be a dictionary type: {}"))
    if "userinfo" in value:
        for key, datadict in value["userinfo"].items():
            if not isinstance(datadict, dict):
                raise ValidationError(
                    _('The "%(key)s" must be a dictionary type: "%(key)s": {"essential": true},'),
                    params={'key': key}
                )
            if "essential" not in datadict:
                raise ValidationError(
                    _('The "%(key)s" value must contain key "essential": "%(key)s": {"essential": true},'),
                    params={'key': key}
                )
            if not isinstance(datadict["essential"], bool):
                raise ValidationError(
                    _('The value of "essential" must be a boolean type": "%(key)s": {"essential": true},'),
                    params={'key': key}
                )


class OIDCHandoverDataBase(CMSPlugin):

    consumer_type = HANDOVER_DATA
    AUTHORIZATION_PROMPT = (
        ('none', _('No interaction')),
        ('login', _('Force login')),
        ('consent', _('Force consent with handovered data')),
    )

    provider = models.ForeignKey(OIDCProvider, on_delete=models.CASCADE)
    claims = jsonfield.JSONField(
        verbose_name=_("Claims"), validators=[validate_claims], help_text=_("Claims attributes for data handover."))
    insist_on_required_claims = models.BooleanField(
        verbose_name=_("Insist on required claims"), default=False,
        help_text=_("Consider the data invalid if not all the required data has been handovered."))
    verified_by = models.CharField(
        verbose_name=_('Verified by names'), max_length=255, null=True, blank=True,
        help_text=_("Verified by names (separated by space)."))
    redirect_page = PageField(verbose_name=_('CMS Page'), blank=True, null=True, on_delete=models.SET_NULL,
                              help_text=_("Redirect to the page after login or hangover data."))
    authorization_prompt = MultiSelectField(
        verbose_name=_('Prompt'), max_length=255, null=True, blank=True, choices=AUTHORIZATION_PROMPT,
        help_text=_('Prompt for user at authorization. "No interaction" cannot be combined with others.'))

    class Meta:
        abstract = True

    def __str__(self):
        return self.provider.name

    def can_login(self):
        return self.consumer_type == LOGIN_USER


class OIDCLoginBase(OIDCHandoverDataBase):
    """OIDC Consumer for login user."""

    consumer_type = LOGIN_USER

    class Meta:
        abstract = True

    no_new_user = models.BooleanField(
        verbose_name=_("No new user"), default=False,
        help_text=_("Do not create a new user account if the user is not recognized."))


class OIDCHandoverData(OIDCHandoverDataBase):
    """OIDC Consumer for data handover."""


class OIDCLogin(OIDCLoginBase):
    """OIDC Consumer for login user."""



CONSUMER_CLASS = {
    HANDOVER_DATA: OIDCHandoverData,
    LOGIN_USER: OIDCLogin,
}


class OIDCIdentifier(CMSPlugin):
    user = models.OneToOneField(getattr(settings, 'AUTH_USER_MODEL', 'auth.User'), on_delete=models.CASCADE)
    provider = models.ForeignKey(OIDCProvider, on_delete=models.CASCADE)
    uident = models.CharField(verbose_name=_('Identifier'), max_length=255, unique=True,
                              help_text=_("Provider unique identifier."))


def get_display_content_settings():
    """Get a list of functions that are used for check conditions for displaying dedicated content."""
    return getattr(settings, 'DJANGOCMS_OIDC_DISPLAY_CONTENT', DEFAULT_DISPLAY_CONTENT)


class OIDCDisplayDedicatedContent(CMSPlugin):
    conditions = models.CharField(
        verbose_name=_('Conditions'),
        help_text=_('Show content only if the given conditions are met.'),
        max_length=255, null=True, blank=True,
        choices=[(key, item[0]) for key, item in get_display_content_settings().items()],
    )


class OIDCShowAttribute(CMSPlugin):
    """Show attribute."""
    verified_by = models.CharField(
        verbose_name=_('Verified by names'), max_length=255, default="name",
        help_text=_("Verified by names (separated by space). Eg.: "
                    "name given_name+family_name preferred_username nickname email openid2_id"))
    default_value = models.CharField(
        verbose_name=_('Default value'), max_length=255, null=True, blank=True,
        help_text=_("Show this text when attribute has not been handovered."))
    css_names = models.CharField(
        verbose_name=_('CSS names'), max_length=255, null=True, blank=True,
        help_text=_("Extra class names (separated by space)."))

    def __str__(self):
        return self.verified_by

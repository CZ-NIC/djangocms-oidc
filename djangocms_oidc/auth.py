import json

import requests
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.translation import ugettext_lazy as _
from mozilla_django_oidc.auth import (LOGGER, OIDCAuthenticationBackend,
                                      SuspiciousOperation)
from mozilla_django_oidc.utils import absolutify
from requests.auth import HTTPBasicAuth

from .constants import DJNAGOCMS_USER_SESSION_KEY
from .helpers import check_required_handovered, get_consumer
from .models import OIDCIdentifier


class DjangocmsOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """Provide OIDC backend with values taken from consumer plugin."""

    def __init__(self, *args, **kwargs):
        """Initialize settings."""
        self.OIDC_OP_TOKEN_ENDPOINT = self.get_settings('OIDC_OP_TOKEN_ENDPOINT', None)  # taken from plugin
        self.OIDC_OP_USER_ENDPOINT = self.get_settings('OIDC_OP_USER_ENDPOINT', None)  # taken from plugin
        self.OIDC_OP_JWKS_ENDPOINT = self.get_settings('OIDC_OP_JWKS_ENDPOINT', None)
        self.OIDC_RP_CLIENT_ID = self.get_settings('OIDC_RP_CLIENT_ID', None)  # taken from plugin
        self.OIDC_RP_CLIENT_SECRET = self.get_settings('OIDC_RP_CLIENT_SECRET', None)  # taken from plugin
        self.OIDC_RP_SIGN_ALGO = self.get_settings('OIDC_RP_SIGN_ALGO', 'HS256')
        self.OIDC_RP_IDP_SIGN_KEY = self.get_settings('OIDC_RP_IDP_SIGN_KEY', None)

        if (self.OIDC_RP_SIGN_ALGO.startswith('RS') and
                (self.OIDC_RP_IDP_SIGN_KEY is None and self.OIDC_OP_JWKS_ENDPOINT is None)):
            msg = '{} alg requires OIDC_RP_IDP_SIGN_KEY or OIDC_OP_JWKS_ENDPOINT to be configured.'
            raise ImproperlyConfigured(msg.format(self.OIDC_RP_SIGN_ALGO))

        self.UserModel = get_user_model()

    def verify_claims(self, claims):
        """Verify the provided claims to decide if authentication should be allowed."""
        scopes = self.get_settings('OIDC_RP_SCOPES', 'openid2_id openid email').split()
        if scopes:
            # At least one of the `scopes` set is present in the `claims`.
            return bool(set(scopes) & set(claims.keys()))
        return True

    def verify_token(self, token, **kwargs):
        """Validate the token signature."""
        nonce = kwargs.get('nonce')

        token = force_bytes(token)
        if self.OIDC_RP_SIGN_ALGO.startswith('RS'):
            if self.OIDC_RP_IDP_SIGN_KEY is not None:
                key = self.OIDC_RP_IDP_SIGN_KEY
            else:
                key = self.retrieve_matching_jwk(token)
        else:
            consumer = get_consumer(self.request)
            if consumer is None:
                return {}
            else:
                key = consumer.provider.get_client_secret()  # OIDC_RP_CLIENT_SECRET

        payload_data = self.get_payload_data(token, key)

        # The 'token' will always be a byte string since it's
        # the result of base64.urlsafe_b64decode().
        # The payload is always the result of base64.urlsafe_b64decode().
        # In Python 3 and 2, that's always a byte string.
        # In Python3.6, the json.loads() function can accept a byte string
        # as it will automagically decode it to a unicode string before
        # deserializing https://bugs.python.org/issue17909
        payload = json.loads(payload_data.decode('utf-8'))
        token_nonce = payload.get('nonce')

        if self.get_settings('OIDC_USE_NONCE', True) and nonce != token_nonce:
            msg = 'JWT Nonce verification failed.'
            raise SuspiciousOperation(msg)
        return payload

    def get_token(self, payload):
        """Return token object as a dictionary."""

        auth = None
        if self.get_settings('OIDC_TOKEN_USE_BASIC_AUTH', False):
            # When Basic auth is defined, create the Auth Header and remove secret from payload.
            user = payload.get('client_id')
            pw = payload.get('client_secret')

            auth = HTTPBasicAuth(user, pw)
            del payload['client_secret']

        consumer = get_consumer(self.request)
        if consumer is None:
            return {}
        response = requests.post(
            consumer.provider.token_endpoint,  # self.OIDC_OP_TOKEN_ENDPOINT,
            data=payload,
            auth=auth,
            verify=self.get_settings('OIDC_VERIFY_SSL', True),
            timeout=self.get_settings('OIDC_TIMEOUT', None),
            proxies=self.get_settings('OIDC_PROXY', None))
        response.raise_for_status()
        return response.json()

    def get_userinfo(self, access_token, id_token, payload):
        """Return user details dictionary. The id_token and payload are not used in
        the default implementation, but may be used when overriding this method"""

        consumer = get_consumer(self.request)
        if consumer is None:
            return {}
        user_response = requests.get(
            consumer.provider.user_endpoint,  # self.OIDC_OP_USER_ENDPOINT,
            headers={
                'Authorization': 'Bearer {0}'.format(access_token)
            },
            verify=self.get_settings('OIDC_VERIFY_SSL', True),
            timeout=self.get_settings('OIDC_TIMEOUT', None),
            proxies=self.get_settings('OIDC_PROXY', None))
        user_response.raise_for_status()
        return user_response.json()

    # This is a copy of the class OIDCAuthenticationBackend with only the change in `get_or_create_user(request, ...)`.
    def authenticate(self, request, **kwargs):
        """Authenticates a user based on the OIDC code flow."""

        self.request = request
        if not self.request:
            return None

        state = self.request.GET.get('state')
        code = self.request.GET.get('code')
        nonce = kwargs.pop('nonce', None)

        if not code or not state:
            return None

        reverse_url = self.get_settings('OIDC_AUTHENTICATION_CALLBACK_URL',
                                        'oidc_authentication_callback')

        consumer = get_consumer(request)
        token_payload = {
            'client_id': consumer.provider.get_client_id(),  # replace OIDC_RP_CLIENT_ID
            'client_secret': consumer.provider.get_client_secret(),  # replace OIDC_RP_CLIENT_SECRET
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': absolutify(
                self.request,
                reverse(reverse_url)
            ),
        }

        # Get the token
        token_info = self.get_token(token_payload)
        id_token = token_info.get('id_token')
        access_token = token_info.get('access_token')

        # Validate the token
        payload = self.verify_token(id_token, nonce=nonce)

        if payload:
            self.store_tokens(access_token, id_token)
            try:
                return self.get_or_create_user(request, access_token, id_token, payload)
            except SuspiciousOperation as exc:
                LOGGER.warning('failed to get or create user: %s', exc)
                return None

        return None

    def set_user_info_into_session(self, request, user_info):
        """Set user_info into session."""
        user_info['user_info_created_at'] = timezone.now().timestamp()
        self.request.session[DJNAGOCMS_USER_SESSION_KEY] = user_info

    def get_or_create_user(self, request, access_token, id_token, payload):
        """Returns a User instance if 1 user is found. Creates a user if not found
        and configured to do so. Returns nothing if multiple users are matched."""

        user_info = self.get_userinfo(access_token, id_token, payload)

        claims_verified = self.verify_claims(user_info)
        if not claims_verified:
            msg = 'Claims verification failed'
            raise SuspiciousOperation(msg)

        consumer = get_consumer(request)
        if consumer is None:
            messages.error(request, _('OIDC Consumer activation failed during authentication. Please try again.'))
            return None

        if consumer.insist_on_required_claims and not check_required_handovered(consumer, user_info):
            messages.error(request, _('Not all required data has been handovered. '
                                      'Please make the transfer again and select all the required values.'))
            return None

        self.set_user_info_into_session(request, user_info)

        if not consumer.can_login():
            # The consumer does not login.
            return None

        if request.user.is_authenticated:
            openid2_id = user_info.get('openid2_id')
            if openid2_id is not None:
                if OIDCIdentifier.objects.filter(uident=openid2_id).exclude(user=request.user).exists():
                    messages.error(
                        request,
                        _("Pairing cannot be performed. This identifier is already paired with another account."))
                    return request.user
            self.create_identifier_if_missing(request, request.user, consumer.provider, openid2_id)
            return request.user
        return self.not_authenticated_user(request, user_info, consumer)

    def create_identifier_if_missing(self, request, user, provider, openid2_id):
        if openid2_id is not None:
            dummy, created = OIDCIdentifier.objects.get_or_create(
                uident=openid2_id, defaults=dict(user=user, provider=provider))
            if created:
                messages.success(request, _('The account has been successfully paired with the provider.'))

    def not_authenticated_user(self, request, user_info, consumer):
        # email based filtering
        users = self.filter_users_by_claims(user_info)
        openid2_id = user_info.get('openid2_id')
        if len(users) == 0:
            if openid2_id:
                users = [ident.user for ident in OIDCIdentifier.objects.filter(uident=openid2_id)]
        if len(users) == 1:
            user = users[0]
            self.create_identifier_if_missing(request, user, consumer.provider, openid2_id)
            if openid2_id:
                user = OIDCIdentifier.objects.get(uident=openid2_id).user
            if not user.is_active:
                msg = _("Your account is deactivated. Please contact our support.")
                messages.error(request, msg)
                return None
            return user
        elif len(users) > 1:
            # In the rare case that two user accounts have the same email address,
            # bail. Randomly selecting one seems really wrong.
            msg = 'Multiple users returned'
            raise SuspiciousOperation(msg)
        elif consumer.can_login():
            if consumer.no_new_user:
                msg = _("To pair with your identity provider, log in first.")
                messages.info(request, msg)
                return None
            user = self.create_user(user_info)
            OIDCIdentifier.objects.get_or_create(user=user, provider=consumer.provider, uident=openid2_id)
            msg = _("A new account has been created with the username {} and email {}.").format(
                user.username, user.email)
            messages.success(request, msg)
            return user
        else:
            LOGGER.debug('Login failed: No user with email %s found.', user_info.get('email'))
            return None

import logging
import time
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _
from mozilla_django_oidc.middleware import SessionRefresh
from mozilla_django_oidc.utils import absolutify

from .helpers import get_consumer

LOGGER = logging.getLogger("djangocms_oidc")


class OIDCSessionRefresh(SessionRefresh):

    def process_request(self, request):
        if not self.is_refreshable_url(request):
            LOGGER.debug('request is not refreshable')
            return

        expiration = request.session.get('oidc_id_token_expiration', 0)
        now = time.time()
        if expiration > now:
            # The id_token is still valid, so we don't have to do anything.
            LOGGER.debug('id token is still valid (%s > %s)', expiration, now)
            return

        LOGGER.debug('id token has expired')
        # The id_token has expired, so we have to re-authenticate silently.
        consumer = get_consumer(request)
        if consumer is None:
            LOGGER.debug('OIDC Consumer was not found in session.')
            messages.error(request, _('OIDC Consumer activation falied. Please try again.'))
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

        state = get_random_string(self.get_settings('OIDC_STATE_SIZE', 32))

        # Build the parameters as if we were doing a real auth handoff, except
        # we also include prompt=none.
        params = {
            'response_type': 'code',
            'client_id': consumer.provider.get_client_id(),
            'redirect_uri': absolutify(
                request,
                reverse(self.get_settings('OIDC_AUTHENTICATION_CALLBACK_URL',
                                          'oidc_authentication_callback'))
            ),
            'state': state,
            'scope': self.get_settings('OIDC_RP_SCOPES', 'openid email'),
            'prompt': 'none',
        }

        if self.get_settings('OIDC_USE_NONCE', True):
            nonce = get_random_string(self.get_settings('OIDC_NONCE_SIZE', 32))
            params.update({
                'nonce': nonce
            })
            request.session['oidc_nonce'] = nonce

        request.session['oidc_state'] = state
        if consumer.redirect_page is None:
            request.session['oidc_login_next'] = request.get_full_path()
        else:
            request.session['oidc_login_next'] = consumer.redirect_page.get_absolute_url()

        query = urlencode(params)
        redirect_url = '{url}?{query}'.format(url=consumer.provider.authorization_endpoint, query=query)
        if request.is_ajax():
            # Almost all XHR request handling in client-side code struggles
            # with redirects since redirecting to a page where the user
            # is supposed to do something is extremely unlikely to work
            # in an XHR request. Make a special response for these kinds
            # of requests.
            # The use of 403 Forbidden is to match the fact that this
            # middleware doesn't really want the user in if they don't
            # refresh their session.
            response = JsonResponse({'refresh_url': redirect_url}, status=403)
            response['refresh_url'] = redirect_url
            return response
        return HttpResponseRedirect(redirect_url)

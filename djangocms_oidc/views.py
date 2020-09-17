import json
from urllib.parse import urlencode, urlparse

from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View
from mozilla_django_oidc.utils import (absolutify,
                                       add_state_and_nonce_to_session,
                                       import_from_settings)
from mozilla_django_oidc.views import (OIDCAuthenticationCallbackView,
                                       OIDCAuthenticationRequestView,
                                       get_next_url)

from .constants import DJNAGOCMS_PLUGIN_SESSION_KEY, DJNAGOCMS_USER_SESSION_KEY
from .helpers import (get_consumer, get_user_identifiers_formset,
                      load_consumer, set_consumer)


class OIDCSignupView(View):
    """View for all consumer types - Login or Handover data."""

    http_method_names = ['get']

    @staticmethod
    def get_settings(attr, *args):
        return import_from_settings(attr, *args)

    def get_redirect_params(self, request, prompt):
        parsed = urlparse(request.META.get('HTTP_REFERER', '/'))
        params = {
            self.get_settings('OIDC_REDIRECT_FIELD_NAME', 'next'): parsed.path
        }
        if prompt:
            params['prompt'] = prompt
        return params

    def get(self, request, consumer_type, plugin_id, prompt=None):
        """Keep plugin ID and redirect to the OIDC consumer."""
        consumer = load_consumer(request, consumer_type, plugin_id)
        if consumer is None:
            messages.error(request, _('OIDC Consumer activation falied. Please try again.'))
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        if consumer.provider.registration_in_progress():
            messages.info(request, _('Communication with the provider is in progress. Please try again later.'))
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        if consumer.provider.needs_register():
            redirect_uris = [request.build_absolute_uri(reverse("oidc_authentication_callback"))]
            error = consumer.provider.register_consumer_into_cache(redirect_uris)
            if error:
                messages.error(request, _('Communication with the provider failed. Please try again later.'))
                messages.error(request, error)
                return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        set_consumer(request, consumer)
        if DJNAGOCMS_USER_SESSION_KEY in request.session:
            del request.session[DJNAGOCMS_USER_SESSION_KEY]
        query = urlencode(self.get_redirect_params(request, prompt))
        redirect_url = '{url}?{query}'.format(url=reverse("oidc_authentication_init"), query=query)
        return HttpResponseRedirect(redirect_url)


class OIDCDismissView(View):
    """Dismiss handovered data."""

    http_method_names = ['get']

    def get(self, request):
        """Remove OIDC data."""
        if DJNAGOCMS_PLUGIN_SESSION_KEY in request.session:
            del request.session[DJNAGOCMS_PLUGIN_SESSION_KEY]
        if DJNAGOCMS_USER_SESSION_KEY in request.session:
            del request.session[DJNAGOCMS_USER_SESSION_KEY]
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))


class OIDCLogoutView(View):
    """Logout view. Return back to the current page after logim. Not to the page with Login form as LoginView does."""

    http_method_names = ['get']

    def get(self, request):
        """Logout user. As a result will be lost also handovered data."""
        if request.user.is_authenticated:
            logout(request)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))


class OIDCDeleteIdentifiersView(View):
    """Delete identifier connected the user with the provider."""

    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        if 'djangocms_oidc_delete_identifier' in request.POST:
            data = {'result': "NOCHANGE"}
            formset = get_user_identifiers_formset(request.user, request.POST, request.FILES)
            if formset.is_valid():
                formset.save()
                if formset.deleted_objects:
                    data['result'] = "SUCCESS"
                    data['messages'] = [_("Identifier has been deleted.")]
            else:
                data['result'] = "ERROR"
                data['messages'] = formset.errors
            if request.is_ajax():
                return JsonResponse(data)
            elif 'messages' in data:
                fnc_messages = messages.success if data['result'] == "SUCCESS" else messages.error
                for msg in data['messages']:
                    fnc_messages(request, msg)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))


class DjangocmsOIDCAuthenticationRequestView(OIDCAuthenticationRequestView):

    def __init__(self, *args, **kwargs):
        # The function is necessary due to supress required OIDC_OP_AUTHORIZATION_ENDPOINT and OIDC_RP_CLIENT_ID
        # in OIDCAuthenticationRequestView.
        super(View, self).__init__(*args, **kwargs)

    def get_extra_params(self, request, consumer):
        params = {}
        if consumer is None:
            claims = self.get_settings('OIDC_AUTH_REQUEST_EXTRA_PARAMS', {})
            if claims:
                params.update(claims)
        else:
            params["claims"] = json.dumps(consumer.claims)
            prompt = set()
            if consumer.authorization_prompt:
                prompt = set(consumer.authorization_prompt)
            prompt_get = request.GET.get('prompt')
            if prompt_get:
                choices = [code for code, _ in consumer.AUTHORIZATION_PROMPT]
                for code in prompt_get.split(","):
                    if code in choices:
                        prompt.add(code)
            if prompt:
                if "none" in prompt and len(prompt) > 1:
                    prompt.remove("none")
                params['prompt'] = " ".join(prompt)
        return params

    def get(self, request):
        """OIDC client authentication initialization HTTP endpoint"""
        state = get_random_string(self.get_settings('OIDC_STATE_SIZE', 32))
        redirect_field_name = self.get_settings('OIDC_REDIRECT_FIELD_NAME', 'next')
        reverse_url = self.get_settings('OIDC_AUTHENTICATION_CALLBACK_URL',
                                        'oidc_authentication_callback')

        consumer = get_consumer(request)
        if consumer is None:
            messages.error(request, _('OIDC Consumer activation falied. Please try again.'))
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        params = {
            'response_type': 'code',
            'scope': self.get_settings('OIDC_RP_SCOPES', 'openid email'),
            'client_id': consumer.provider.get_client_id(),  # OIDC_RP_CLIENT_ID
            'redirect_uri': absolutify(
                request,
                reverse(reverse_url)
            ),
            'state': state,
        }
        if self.get_settings('OIDC_USE_NONCE', True):
            nonce = get_random_string(self.get_settings('OIDC_NONCE_SIZE', 32))
            params.update({
                'nonce': nonce
            })
            request.session['oidc_nonce'] = nonce

        add_state_and_nonce_to_session(request, state, params)

        if consumer.redirect_page is None:
            request.session['oidc_login_next'] = get_next_url(request, redirect_field_name)
        else:
            request.session['oidc_login_next'] = consumer.redirect_page.get_absolute_url()

        params.update(self.get_extra_params(request, consumer))
        query = urlencode(params)
        redirect_url = '{url}?{query}'.format(url=consumer.provider.authorization_endpoint, query=query)
        return HttpResponseRedirect(redirect_url)


class DjangocmsOIDCAuthenticationCallbackView(OIDCAuthenticationCallbackView):

    @property
    def failure_url(self):
        consumer = get_consumer(self.request)
        if consumer is not None and consumer.can_login():
            messages.info(self.request, _("Login failed."))
        next_url = self.request.session.get('oidc_login_next', None)
        return next_url or self.get_settings('LOGIN_REDIRECT_URL_FAILURE', '/')

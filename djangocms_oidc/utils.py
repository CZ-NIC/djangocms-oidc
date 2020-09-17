from django.utils.translation import ugettext_lazy as _
from cms.utils.conf import get_cms_setting
from mozilla_django_oidc.utils import import_from_settings


def get_settings(attr, *args):
    return import_from_settings(attr, *args)


def get_cache_key(key):
    return "{}{}".format(get_cms_setting('CACHE_PREFIX'), key)


def only_authenticated_user(context, instance, placeholder, user_info):
    return context['request'].user.is_authenticated


def email_verified(context, instance, placeholder, user_info):
    if user_info is None:
        return False
    messages = []
    if not user_info.get('email'):
        messages.append(_("Email missing."))
    if not user_info.get('email_verified'):
        messages.append(_("Email is not verified."))
    if messages:
        context['dedicated_content'] = "<ul class='messagelist'><li class='error'>{}</li></ul>".format(
            " ".join(messages))
    return len(messages) == 0


DEFAULT_DISPLAY_CONTENT = {
    'only_authenticated_user': (_('Only authenticated user'), only_authenticated_user),
    'email_verified': (_('Email verified'), email_verified),
}

from cms.utils.conf import get_cms_setting
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _
from mozilla_django_oidc.utils import import_from_settings


def get_settings(attr, *args):
    return import_from_settings(attr, *args)


def get_cache_key(key):
    return "{}{}".format(get_cms_setting('CACHE_PREFIX'), key)


def only_user_is_staff(context, instance, placeholder, user_info):
    request = context['request']
    return hasattr(request, "user") and request.user.is_staff


def only_authenticated_user(context, instance, placeholder, user_info):
    request = context['request']
    return hasattr(request, "user") and request.user.is_authenticated


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
            " ".join([force_str(msg) for msg in messages]))
    return len(messages) == 0


DEFAULT_DISPLAY_CONTENT = [
    # (Choice code, choice label, function)
    ('only_authenticated_user', _('Only authenticated user'), only_authenticated_user),
    ('only_user_is_staff', _('Only user is staff'), only_user_is_staff),
    ('email_verified', _('Email verified'), email_verified),
]

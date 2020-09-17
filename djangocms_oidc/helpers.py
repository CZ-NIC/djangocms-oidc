import re

from django.core.exceptions import ObjectDoesNotExist
from django.forms import modelformset_factory
from django.utils.encoding import force_text

from .constants import DJNAGOCMS_USER_SESSION_KEY, DJNAGOCMS_PLUGIN_SESSION_KEY
from .models import CONSUMER_CLASS, OIDCIdentifier


def set_consumer(request, instance):
    """Set consumer into session."""
    request.session[DJNAGOCMS_PLUGIN_SESSION_KEY] = (instance.consumer_type, instance.pk)


def get_consumer(request):
    """Get consumer from session."""
    plugin_type_and_id = request.session.get(DJNAGOCMS_PLUGIN_SESSION_KEY)
    if plugin_type_and_id is not None:
        consumer_type, instance_id = plugin_type_and_id
        try:
            return CONSUMER_CLASS[consumer_type].objects.get(pk=instance_id)
        except ObjectDoesNotExist:
            pass
    return None


def load_consumer(request, consumer_type, instance_id):
    """Load consumer according of type and ID."""
    if consumer_type in CONSUMER_CLASS:
        try:
            return CONSUMER_CLASS[consumer_type].objects.get(pk=instance_id)
        except ObjectDoesNotExist:
            pass
    return None


def get_user_identifiers_formset(user, post=None, files=None):
    """Get OIDCIdentifier formset."""
    IdentifierFormSet = modelformset_factory(OIDCIdentifier, fields=(), extra=0, can_delete=True)
    return IdentifierFormSet(post, files, queryset=OIDCIdentifier.objects.filter(user=user))


def check_required_handovered(consumer, user_info):
    """Check that all required data has been handovered."""
    for key, data in consumer.claims.get('userinfo', {}).items():
        if data['essential'] and key not in user_info:
            return False
    return True


def get_verified_as(verified_by, user_info, default):
    """Collect values from user_info and attributes definitions."""
    name = default
    if verified_by is not None:
        names = []
        for item in re.split(r'\s+', verified_by):
            for key in item.split('+'):
                value = user_info.get(key)
                if value:
                    names.append(force_text(value))
            if names:
                name = " ".join(names)
                break
    return name


def get_user_info(request):
    """Get user info stored in session."""
    return request.session.get(DJNAGOCMS_USER_SESSION_KEY)


def clear_user_info(request):
    """Delete user info stored in session."""
    request.session.pop(DJNAGOCMS_USER_SESSION_KEY, None)

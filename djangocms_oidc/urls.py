from django.urls import path, re_path
from django.utils.module_loading import import_string
from mozilla_django_oidc.utils import import_from_settings

from .models import CONSUMER_CLASS
from .views import OIDCDeleteIdentifiersView, OIDCLogoutView

DEFAULT_SIGNUP_VIEW_CLASS = 'djangocms_oidc.views.OIDCSignupView'
SIGNUP_VIEW_CLASS_PATH = import_from_settings('DJANGOCMS_OIDC_SIGNUP_VIEW_CLASS', DEFAULT_SIGNUP_VIEW_CLASS)
OIDCCSignupViewClass = import_string(SIGNUP_VIEW_CLASS_PATH)

DEFAULT_DISMISS_VIEW_CLASS = 'djangocms_oidc.views.OIDCDismissView'
DISMISS_VIEW_CLASS_PATH = import_from_settings('DJANGOCMS_OIDC_DISMISS_VIEW_CLASS', DEFAULT_DISMISS_VIEW_CLASS)
OIDCDismissViewClass = import_string(DISMISS_VIEW_CLASS_PATH)

urlpatterns = [
    re_path(r'^oidc-sign-up/(?P<consumer_type>({}))-(?P<plugin_id>\d+)(?P<prompt>[\w,]+)?/$'.format(
        '|'.join(CONSUMER_CLASS.keys())),
        OIDCCSignupViewClass.as_view(), name='djangocms_oidc_signup'),
    path('oidc-dismiss/', OIDCDismissViewClass.as_view(), name='djangocms_oidc_dismiss'),
    path('oidc-logout/', OIDCLogoutView.as_view(), name='djangocms_oidc_logout'),
    path('oidc-delete-identifiers/', OIDCDeleteIdentifiersView.as_view(), name='djangocms_oidc_delete_identifiers'),
]

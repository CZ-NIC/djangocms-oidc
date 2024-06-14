from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OidcAppConfig(AppConfig):
    name = "djangocms_oidc"
    verbose_name = _("OIDC authentication")

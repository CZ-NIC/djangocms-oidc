from django.contrib import admin

from ..models import OIDCIdentifier, OIDCProvider, OIDCRegisterConsumer
from .options import OIDCIdentifierAdmin, OIDCProviderAdmin, OIDCRegisterConsumerAdmin

admin.site.register(OIDCRegisterConsumer, OIDCRegisterConsumerAdmin)
admin.site.register(OIDCProvider, OIDCProviderAdmin)
admin.site.register(OIDCIdentifier, OIDCIdentifierAdmin)

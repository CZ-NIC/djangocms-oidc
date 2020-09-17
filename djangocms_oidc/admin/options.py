from django.contrib import admin

from .forms import OIDCProviderForm


class OIDCIdentifierAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_email', 'provider', 'uident')

    def user_email(self, obj):
        return obj.user.email


class OIDCRegisterConsumerAdmin(admin.ModelAdmin):
    list_display = ('name', 'register_url')


class OIDCProviderAdmin(admin.ModelAdmin):
    form = OIDCProviderForm

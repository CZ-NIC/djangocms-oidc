from django.http import HttpResponse
from django.views.generic import View


class TestHomePage(View):

    def get(self, request, *args, **kwargs):
        return HttpResponse(b"Test Home page.")


class TestLoginPage(View):

    def get(self, request, *args, **kwargs):
        return HttpResponse(b"Test Login page.")


class TestFakePage(View):

    def get(self, request, *args, **kwargs):
        return HttpResponse(b"Win!")

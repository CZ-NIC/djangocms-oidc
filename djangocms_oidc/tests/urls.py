from cms.views import details
from django.urls import path, re_path
from mozilla_django_oidc.urls import urlpatterns as mozilla_urlpatterns

from djangocms_oidc.tests.views import TestFakePage, TestHomePage, TestLoginPage
from djangocms_oidc.urls import urlpatterns as djangocms_oidc_urlpatterns

urlpatterns = [
    path('', TestHomePage.as_view(), name='test_home_page'),
    path('login/', TestLoginPage.as_view(), name='login'),
    path('mdo_fake_view/', TestFakePage.as_view(), name='mdo_fake_view'),
]
urlpatterns.extend(mozilla_urlpatterns)
urlpatterns.extend(djangocms_oidc_urlpatterns)
urlpatterns.append(re_path(r'^(?P<slug>[0-9A-Za-z-_.//]+)/$', details, name='pages-details-by-slug'))

from cms.views import details
from django.conf.urls import url
from mozilla_django_oidc.urls import urlpatterns as mozilla_urlpatterns

from djangocms_oidc.tests.views import TestFakePage, TestHomePage, TestLoginPage
from djangocms_oidc.urls import urlpatterns as djangocms_oidc_urlpatterns

urlpatterns = [
    url(r'^$', TestHomePage.as_view(), name='test_home_page'),
    url(r'^login/$', TestLoginPage.as_view(), name='login'),
    url(r'^mdo_fake_view/$', TestFakePage.as_view(), name='mdo_fake_view'),
]
urlpatterns.extend(mozilla_urlpatterns)
urlpatterns.extend(djangocms_oidc_urlpatterns)
urlpatterns.append(url(r'^(?P<slug>[0-9A-Za-z-_.//]+)/$', details, name='pages-details-by-slug'))

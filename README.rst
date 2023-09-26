|Build Status| |Coverage| |Pypi package| |Pypi status| |Python versions| |License|


===============================
DjangoCMS OIDC (OpenID Connect)
===============================

Plugins for user authentication via OpenID, based on `Mozilla Django OIDC <https://github.com/mozilla/mozilla-django-oidc/>`_.


Installation
============

.. code-block:: shell

    $ pip install djangocms-oidc


Caution! If you are using project `django-python3-ldap <https://github.com/etianen/django-python3-ldap>`_, you must use version higher than ``0.11.3``.

Example in ``requirements.txt``:

.. code-block:: python

    django-python3-ldap @ git+https://github.com/etianen/django-python3-ldap.git@759d3483d9e656fef2b6a2e669101bca3021d9d5


Add settings to settings.py
---------------------------

Start by making the following changes to your ``settings.py`` file.

.. code-block:: python

   # Add 'mozilla_django_oidc' and 'djangocms_oidc' to INSTALLED_APPS
   INSTALLED_APPS = [
       # ...
       'multiselectfield',
       'django_countries',
       'mozilla_django_oidc',  # place after auth (django.contrib.auth)
       'djangocms_oidc',
   ]

   AUTHENTICATION_BACKENDS = [
       # ...
       'djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend',
   ]

   MIDDLEWARE = [
       # ...
       'djangocms_oidc.middleware.OIDCSessionRefresh',
   ]

   # Define OIDC classes
   OIDC_AUTHENTICATE_CLASS = "djangocms_oidc.views.DjangocmsOIDCAuthenticationRequestView"
   OIDC_CALLBACK_CLASS = "djangocms_oidc.views.DjangocmsOIDCAuthenticationCallbackView"
   OIDC_OP_AUTHORIZATION_ENDPOINT = "https://example.com/authorization-endpoint"
   OIDC_RP_CLIENT_ID = "myClientId"


Add OIDC urls to urls.py
---------------------------

Modify your project ``urls.py`` file.

.. code-block:: python

    urlpatterns = [
        # ....
        path('oidc/', include('mozilla_django_oidc.urls')),
        path('djangocms-oidc/', include('djangocms_oidc.urls')),
    ]


Settings
========

Most settings are the same as the project `Mozilla Django OIDC <https://github.com/mozilla/mozilla-django-oidc/>`_.

The following values are defined in the plugins. It is therefore not necessary to set them in the project settings. They have no effect.

    * ``OIDC_RP_CLIENT_ID``
    * ``OIDC_RP_CLIENT_SECRET``
    * ``OIDC_OP_AUTHORIZATION_ENDPOINT``
    * ``OIDC_OP_TOKEN_ENDPOINT``
    * ``OIDC_OP_USER_ENDPOINT``

The ``OIDC_RP_SCOPES`` parameter behaves differently from the parameter in ``mozilla-django-oidc``
due to overloaded function ``verify_claims``. The parameter contains a string of claim names.
If at least one of them is present in the response from the provider, the handover of the data is verified.
Default value of parameter is ``'openid2_id openid email'``.
One of these data must be handovered, otherwise the response from the provider is dismissed.


Usage in administration
=======================

These plugins are available to the editor in the administration:

  * OIDC Handover data
  * OIDC Login
  * OIDC List identifiers
  * OIDC Display dedicated content
  * OIDC Show attribute
  * OIDC Show attribute Country

How to use provider MojeID
==========================

Home › Djangocms_Oidc › Oidc register consumers › oidc register consumer: Add

 | Name: MojeID Test
 | Register consumer: https://mojeid.regtest.nic.cz/oidc/registration/


Home › Djangocms_Oidc › Oidc providers › oidc provider: add

 | Name: MojeID Test
 | Code: mojeid
 | Register consumer: MojeID Test
 | Authorization endpoint: https://mojeid.regtest.nic.cz/oidc/authorization/
 | Token endpoint: https://mojeid.regtest.nic.cz/oidc/token/
 | User endpoint: https://mojeid.regtest.nic.cz/oidc/userinfo/
 | Account URL: https://mojeid.regtest.nic.cz/editor/
 | Logout URL: https://mojeid.regtest.nic.cz/logout/

Page structure: Add

 | OpenID Connect: OIDC Handover data
 | Provider: MojeID Test
 | Claims: {...} (copy from the example below) For mojeid see list "claims_supported" in .well-known `openid-configuration <https://mojeid.cz/.well-known/openid-configuration>`_.
 | Verified by names: ... (copy from the example below)


How to run an example
=====================

Run the example in Docker. Install as follows:

.. code-block:: shell

    $ git clone https://github.com/CZ-NIC/djangocms-oidc-form-fields.git
    $ cd djangocms-oidc-form-fields/example
    $ docker-compose build web
    $ docker-compose run --user $(id -u):$(id -g) web python manage.py migrate
    $ docker-compose run --user $(id -u):$(id -g) web python manage.py loaddata site.json

Start the webserver:

.. code-block:: shell

    $ docker-compose up -d

Open in your browser: http://localhost:8000/. To log in to the administrations use ``admin:password`` at http://localhost:8000/admin.

Stop the webserver:

.. code-block:: shell

    $ docker-compose down

License
-------

This software is licensed under the GNU GPL license. For more info check the LICENSE file.


.. |Build Status| image:: https://travis-ci.org/CZ-NIC/djangocms-oidc.svg?branch=master
    :target: https://travis-ci.org/CZ-NIC/djangocms-oidc
    :alt: Build Status
.. |Coverage| image:: https://codecov.io/gh/CZ-NIC/djangocms-oidc/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/CZ-NIC/djangocms-oidc
    :alt: Coverage
.. |Pypi package| image:: https://img.shields.io/pypi/v/djangocms-oidc.svg
    :target: https://pypi.python.org/pypi/djangocms-oidc/
    :alt: Pypi package
.. |Pypi status| image:: https://img.shields.io/pypi/status/djangocms-oidc.svg
   :target: https://pypi.python.org/pypi/djangocms-oidc
   :alt: status
.. |Python versions| image:: https://img.shields.io/pypi/pyversions/djangocms-oidc.svg
   :target: https://pypi.python.org/pypi/djangocms-oidc
   :alt: Python versions
.. |License| image:: https://img.shields.io/pypi/l/djangocms-oidc.svg
    :target: https://pypi.python.org/pypi/djangocms-oidc/
    :alt: license

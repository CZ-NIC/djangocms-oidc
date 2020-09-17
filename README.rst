===============================
DjangoCMS OIDC (OpenID Connect)
===============================

Plugins for user authentication via OpenID, based on `Mozilla Django OIDC <https://github.com/mozilla/mozilla-django-oidc/>`_.


Installation
============

.. code-block:: shell

    $ pip install git+https://github.com/CZ-NIC/djangocms-oidc@28230-create-plugin


Caution! If you are using project `django-python3-ldap <https://github.com/etianen/django-python3-ldap>`_, you must use version higher than ``0.11.3``.

Example in ``requirements.txt``:

.. code-block:: python

    django-python3-ldap @ git+https://github.com/etianen/django-python3-ldap.git@759d3483d9e656fef2b6a2e669101bca3021d9d5


Add settings to settings.py
---------------------------

Start by making the following changes to your ``settings.py`` file.

.. code-block:: python

   # Add 'mozilla_django_oidc' and 'djangocms_oidc' to INSTALLED_APPS
   INSTALLED_APPS = (
       # ...
       'multiselectfield',
       'django_countries',
       'mozilla_django_oidc',  # place after auth (django.contrib.auth)
       'djangocms_oidc',
       # ...
   )

   AUTHENTICATION_BACKENDS = (
       # ...
       'djangocms_oidc.auth.DjangocmsOIDCAuthenticationBackend',
       # ...
   )

   MIDDLEWARE = (
       # ...
       'djangocms_oidc.middleware.OIDCSessionRefresh',
       # ...
   )

   # Define OIDC classes
   OIDC_AUTHENTICATE_CLASS = "djangocms_oidc.views.DjangocmsOIDCAuthenticationRequestView"
   OIDC_CALLBACK_CLASS = "djangocms_oidc.views.DjangocmsOIDCAuthenticationCallbackView"


Add OIDC urls to urls.py
---------------------------

Modify your project ``urls.py`` file.

.. code-block:: python

    urlpatterns = [
        # ....
        url(r'^oidc/', include('mozilla_django_oidc.urls')),
        url(r'^djangocms-oidc/', include('djangocms_oidc.urls')),
        # ....
    ]



Example of installation
=======================

You can test in python virtual environment. This does not have any affest to your current python installation of packages.

Create python virtual environment and activate it:

.. code-block:: shell

    $ virtualenv --python=/usr/bin/python3 env
    $ source env/bin/activate

Install DjangoCMS and this projects:

.. code-block:: shell

    $ pip install djangocms-installer
    $ pip install git+https://github.com/CZ-NIC/djangocms-oidc@28230-create-plugin

Create CMS testing site and go to the main project folder:

.. code-block:: shell

    $ djangocms mysite

Modify settings and urls with the `mysite.patch <accessories/mysite.patch>`_:

.. code-block:: shell

    $ patch -p0 < mysite.patch

Migrage new installed plugins:

.. code-block:: shell

    $ cd mysite
    $ python manage.py migrate


Run test server:

.. code-block:: shell

    $ python manage.py runserver



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


License
-------

This software is licensed under the GNU GPL license. For more info check the LICENSE file.


More information
----------------

You can get the code from the `project site <https://github.com/CZ-NIC/djangocms-oidc>`_.

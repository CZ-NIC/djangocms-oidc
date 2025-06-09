# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [5.0.0] - 2025-06-09

- Upgrade versions to django-cms 4.1.
- Restrict to python version 3.10.

## [4.2.0] - 2024-06-18

- Add OidcAppConfig and verbose_name_plural.
- Set custom field OIDCDisplayDedicatedContentPlugin.name by settings DJANGOCMS_OIDC_DISPLAY_DEDICATED_CONTENT_NAME.

## [4.1.2] - 2024-05-28

- Display dedicated content only to editors in edit mode.

## [4.1.1] - 2024-05-27

- Add get_default_claim.

## [4.1.0] - 2024-05-27

- Use widget JsonDataTextarea for field claim.

## [4.0.0] - 2023-09-26

- Upgrade versions to django-cms 3.11.

## [3.0.1] - 2022-02-15

- Ticket #32550 - Catch SuspiciousOperation (invalid nonce) in verify_token in DjangocmsOIDCAuthenticationBackend.authenticate.
- Ticket #32550 - Fix raise Unauthorized HttpError.

## [3.0.0] - 2021-03-26

- Add field button_label into model OIDCHandoverDataBase.
- Output error messages when consumer missing in cache in authenticate.
- Remove support of Python 3.5 and 3.6 from tox and travis.

## [2.0.0] - 2020-11-04

- Add Travis, tests, tox.
- Update patch.

## [1.0.0] - 2020-09-17

### Added
- Create a group of plugins to manage OIDC consumer.


[Unreleased]: https://github.com/CZ-NIC/djangocms-oidc/compare/5.0.0...master
[5.0.0]: https://github.com/CZ-NIC/djangocms-oidc/compare/4.2.0...5.0.0
[4.2.0]: https://github.com/CZ-NIC/djangocms-oidc/compare/4.1.2...4.2.0
[4.1.2]: https://github.com/CZ-NIC/djangocms-oidc/compare/4.1.1...4.1.2
[4.1.1]: https://github.com/CZ-NIC/djangocms-oidc/compare/4.1.0...4.1.1
[4.1.0]: https://github.com/CZ-NIC/djangocms-oidc/compare/4.0.0...4.1.0
[4.0.0]: https://github.com/CZ-NIC/djangocms-oidc/compare/3.0.1...4.0.0
[3.0.1]: https://github.com/CZ-NIC/djangocms-oidc/compare/3.0.0...3.0.1
[3.0.0]: https://github.com/CZ-NIC/djangocms-oidc/compare/2.0.0...3.0.0
[2.0.0]: https://github.com/CZ-NIC/djangocms-oidc/compare/1.0.0...2.0.0
[1.0.0]: https://github.com/CZ-NIC/djangocms-oidc/compare/175837c66f275e98957a9c542600bc58671ca4cb...1.0.0

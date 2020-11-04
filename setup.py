# -*- coding: utf-8 -*-
from distutils.command.build import build

from setuptools import find_packages, setup
from setuptools.command.sdist import sdist


class CustomBuild(build):
    sub_commands = [("compile_catalog", lambda x: True)] + build.sub_commands


setup(
    author='Zdeněk Böhm',
    author_email='zdenek.bohm@nic.cz',
    name='djangocms-oidc',
    version='2.0.0',
    description='Plugin OIDC (OpenID Connect) into Django CMS.',
    url='https://github.com/CZ-NIC/djangocms-oidc',
    license='GPL GNU License',
    platforms=['OS Independent'],
    classifiers=(
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Framework :: DjangoCMS',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Framework :: Django CMS',
        'Framework :: Django CMS :: 3.7',
    ),
    install_requires=(
        'django-cms==3.7.4',
        'mozilla-django-oidc==1.2.4',
        'django-jsonfield',
        'django-countries',
        'django-multiselectfield',
    ),
    extras_require={
        'quality': ['isort', 'flake8'],
        'test': ['requests_mock', 'freezegun'],
    },
    packages=find_packages(exclude=['tests']),
    cmdclass={"build": CustomBuild},
    setup_requires=["Babel >=2.3"],
    include_package_data=True,
    zip_safe=False
)

from distutils.command.build import build

from setuptools import find_packages, setup


class CustomBuild(build):
    sub_commands = [("compile_catalog", lambda x: True)] + build.sub_commands


setup(
    author='Zdeněk Böhm',
    author_email='zdenek.bohm@nic.cz',
    name='djangocms-oidc',
    version='4.0.0',
    description='Plugin OIDC (OpenID Connect) into Django CMS.',
    long_description=open('README.rst').read(),
    long_description_content_type='text/x-rst',
    url='https://github.com/CZ-NIC/djangocms-oidc',
    license='GPL GNU License',
    platforms=['OS Independent'],
    classifiers=(
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Framework :: Django CMS :: 3.11',
    ),
    install_requires=(
        'django-cms~=3.11',
        'mozilla-django-oidc~=3.0',
        'django-countries~=7.5',
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

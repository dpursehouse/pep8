# Django settings for cm_web project.

import os
import sys

PATH_CM_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(PATH_CM_TOOLS, 'external-modules') not in sys.path:
    sys.path.insert(0, os.path.join(PATH_CM_TOOLS, 'external-modules'))
if os.path.join(PATH_CM_TOOLS, 'semcwikitools') not in sys.path:
    sys.path.insert(0, os.path.join(PATH_CM_TOOLS, 'semcwikitools'))
if PATH_CM_TOOLS not in sys.path:
    sys.path.insert(0, PATH_CM_TOOLS)

PATH_GITS = os.path.join(os.path.dirname(PATH_CM_TOOLS), 'gits')
PATH_MANIFEST = os.path.join(PATH_GITS, 'platform/manifest')

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

# use PostgreSQL in prod env. Use SQLite in dev env.
if __file__.find('/home/') != 0:
    DATABASE_ENGINE = 'postgresql_psycopg2'
else:
    DATABASE_ENGINE = 'sqlite3'

DATABASE_NAME = 'cm_web_db'
DATABASE_USER = ''
DATABASE_PASSWORD = ''
DATABASE_HOST = ''
DATABASE_PORT = ''

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
# TIME_ZONE = 'America/Chicago'
TIME_ZONE = 'UTC'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media/')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/admin_media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'et!%*cuqx6$187wyu10i!45^j*v!8g1vae-o@cj!%u$3vi6ond'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)

ROOT_URLCONF = 'cm_web.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates"
    # or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(os.path.dirname(__file__), 'templates')
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'cm_web.matrix'
)

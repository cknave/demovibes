# Django settings for demovibes project.

import os
import django
# calculated paths for django and the site
# used as starting points for various other paths
DJANGO_ROOT = os.path.dirname(os.path.realpath(django.__file__))
SITE_ROOT = os.path.dirname(os.path.realpath(__file__))
SITE_ROOT = os.path.dirname(SITE_ROOT)

def pj(*path):
    return os.path.join(SITE_ROOT, *path)

from smileys import SMILEYS

LOGIN_URL = "/demovibes/login/"

DEBUG = True
TEMPLATE_DEBUG = False

#For looking up flag country on users with no flag set
LOOKUP_COUNTRY = True
DEFAULT_FLAG = "nectaflag"

#To make this work you need:
#  1. uWSGI
#  2. start the uwsgi_eventhandler module
#  3. Point /demovibes/ajax/monitor/* urls to it
#UWSGI_EVENT_SERVER = ("127.0.0.1", 3032)
#
#If you have vserver that need a specific url, use this:
#UWSGI_EVENT_SERVER_HTTP = "http://<hostname>/demovibes/ajax/monitor/new/"
# Remember to also add ip to allowed_ips in uwsgi_eventhandler/local_settings.py

#from django.conf import global_settings
#FILE_UPLOAD_HANDLERS = ('webview.uploadprogress.UploadProgressCachedHandler', ) + \
#    global_settings.FILE_UPLOAD_HANDLERS

## Decides if a user can vote on and request his own songs
#SONG_SELFQUEUE_DISABLED = False
#SONG_SELFVOTE_DISABLED = False

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

HAYSTACK_SITECONF = 'demovibes.search_sites'
HAYSTACK_SEARCH_ENGINE = "whoosh"
HAYSTACK_WHOOSH_PATH = pj("local","whoosh")

DATABASE_ENGINE = 'sqlite3'           # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_NAME = pj('sqlite.db')             # Or path to database file if using sqlite3.
DATABASE_USER = ''             # Not used with sqlite3.
DATABASE_PASSWORD = ''         # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

# Search results per type (group, artist, songs)
SEARCH_LIMIT = 40

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/Oslo'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

ACCOUNT_ACTIVATION_DAYS = 7

# There may be a situation where your server doesn't have a built-in SMTP server, and you
# Wish to use a 3rd party SMTP server. Uncommenting these boxes and setting them accordingly
# Will allow this to take place. The default SMTP options may not deliver to outside world, in
# Which case, use this instead. AAK.

# Host for sending e-mail. This would be the SMTP host for your email provider
#EMAIL_HOST = ''
#DEFAULT_FROM_EMAIL = ""

# Port for sending e-mail. By default, it is almost always 25.
#EMAIL_PORT = 25

# Optional SMTP authentication information for EMAIL_HOST. Some SMTP servers require the
# Authoriazation to be the same as the email address for the count, and work better using
# The + chanarcter instead of @.
#EMAIL_HOST_USER = 'smtpuser+domain.com'
#EMAIL_HOST_PASSWORD = 'smtp_password'
#EMAIL_USE_TLS = False

# END SMTP Configuration

# Cherokee secure url shared key
# If empty, disable
# The secure url root should point to static folder.
# See http://www.cherokee-project.com/doc/modules_handlers_secdownload.html for more info
CHEROKEE_SECRET_DOWNLOAD_KEY=""
CHEROKEE_SECRET_DOWNLOAD_PATH=""
# IF defined, will alter default file url with re.sub(r1, r2, url)
#CHEROKEE_SECRET_DOWNLOAD_REGEX=(r'', r'')
# If defined, will limit number of generated links per user to X links per Y seconds
#CHEROKEE_SECRET_DOWNLOAD_LIMIT={'number': X, 'seconds': Y}
# Or, more specified:
#CHEROKEE_SECRET_DOWNLOAD_LIMIT={
#    'admin': {'number': 30, 'seconds': 60*60*24},
#    'Group name': {'number': 15, 'seconds': 60*60*24},
#    'default': {'number': 0, 'seconds': 60*60*24},
#    'staff': {'number': 3, 'seconds': 60*60*24},
#}
# URL to redirect to if limit is reached
#CHEROKEE_SECRET_DOWNLOAD_LIMIT_URL="/static/badman.html"

# maximum time a song will be played in seconds
# only used when demosauce streamer is used
# default fadeout is right before knucklebusters gets ugly
# comment out or set to zero to disable
#MAX_SONG_LENGTH = 480

#location of demosauce scan tool
DEMOSAUCE_SCAN = '../demosauce/scan'

# a value that decides if a module is likely to be loopded. 0.1 seems to be good for starters
# only required if demosauce scan is used
LOOPINESS_THRESHOLD = 0.1

# time a song is looped in seconds
# this ONLY applies to modules (.mod, .xm, etc...) AND if a loop has been detected
# only required if demosauce scan is used
LOOP_LENGTH = 150

# Customize the dimensions on the avatars used on the site. AVATAR_SIZE is a value in
# Bytes that the image file cannot exceed. Reccomend no less than 40Kb so users can have
# Some pretty AnimGIF files to use. HEIGHT and WIDTH are specified in pixels.
MAX_AVATAR_SIZE = 65536
MAX_AVATAR_HEIGHT = 100
MAX_AVATAR_WIDTH = 100

# Artist pictures can also be customized to fit your site using these values
MAX_ARTIST_AVATAR_SIZE = 65536
MAX_ARTIST_AVATAR_HEIGHT = 200
MAX_ARTIST_AVATAR_WIDTH = 200

# Group Logo controls
MAX_GROUP_AVATAR_SIZE = 65536
MAX_GROUP_AVATAR_HEIGHT = 250
MAX_GROUP_AVATAR_WIDTH = 250

# Max internal length of the oneliner, in characters
MAX_ONELINER_LENGTH = 256

# In the updates page, you can limit the number of entries displayed for each category by
# Adjusting these values accordingly.
RECENT_ARTIST_VIEW_LIMIT  = 20
RECENT_SONG_VIEW_LIMIT    = 20
RECENT_LABEL_VIEW_LIMIT   = 20
RECENT_GROUP_VIEW_LIMIT   = 20
RECENT_COMP_VIEW_LIMIT    = 20

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = DOCUMENT_ROOT = pj('static')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/static/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Please set a backend here
# We recommend memcached.
# If that's not avaliable we recommend file or database cache,
# because locmem can't always be trusted to have a consistent cache
#CACHE_BACKEND = 'memcached://127.0.0.1:11211/'
CACHE_BACKEND = 'dummy://'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'replaceThis!'

AUTH_PROFILE_MODULE = 'webview.userprofile'

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
 #add ?profiler to url to get a profile of the page. Debug needs to be on
)

ROOT_URLCONF = 'demovibes.urls'

# New changes introduced to demovibes to support user/global template changes. The
# Local folder should always be checked first for user customized templates. In the
# Event that this fails, then the global template is used instead. AAK.
TEMPLATE_DIRS = (
    pj('templates', 'local'),
    pj('templates', 'global'),
    pj('templates', 'jinja', 'local'),
    pj('templates', 'jinja', 'global'),
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

JINJA2_TEMPLATE_DIRS = (
    pj('templates', 'jinja', 'local'),
    pj('templates', 'jinja', 'global'),
)

JINJA2_EXTENSIONS = ["jinja2.ext.i18n"]

# Maximum number of songs a user can have in the queue at the same time.
SONGS_IN_QUEUE = 5

# Optional filter for how many songs of "lowvote" or lower user can have in queue
#SONGS_IN_QUEUE_LOWRATING = {'limit': 1, 'lowvote':2}

# Time to lock a song until it can be requested again.
SONG_LOCK_TIME = { 'days' : 0, 'hours' : 0, 'minutes' : 5 }

# Need to have at least one song marked as jingle for this to work
# Will play one every 30 minutes or 10 songs, but not more often than every 20 minutes.
PLAY_JINGLES = False

# How many objects per page:
PAGINATE = 30
FORUM_PAGINATE = 15

# When displaying approved songs, specify the maximum number to display on the page here.
# You should take into account that you will want to display about an average of 2 days worth
# Of uploads; Otherwise the list will never be useful except at the time a new batch of
# Large songs are approved. AAK
UPLOADED_SONG_COUNT = 150

# You can specify if you want shortened url's in the oneliner. If enabled, it will take
# A link such as http://www.blah.com/blah/bleh/blob.html and make a clickable link to
# Only http://www.blah.com in the display portion, the clicked link contains the full path.
# Set to a value of 1 to enable truncated links.
SHORTEN_ONELINER_LINKS = 0

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.core.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.request",
)

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'demovibes.webview',
    'demovibes.registration',
    'demovibes.forum',
    'django.contrib.markup',
    'south',
    'tagging',
    'django_extensions',
    'haystack',
    'openid_provider',
    'demovibes.search',
]

try:
    import django_wsgiserver
    INSTALLED_APPS.append("django_wsgiserver")
except:
    pass

## SMILEY LIMITS
##
# Note that total is not hard limit, and can in some cases
# allow (PER_SMILEY_LIMIT - 1) smileys extra

#ONELINER_PER_SMILEY_LIMIT = 0
#ONELINER_TOTAL_SMILEY_LIMIT = None
#OTHER_PER_SMILEY_LIMIT = 0
#OTHER_TOTAL_SMILEY_LIMIT = None


# demosauce scan requires this. terra said there were problems...
# but when I tested it I didn't see any
# in django it looks like that: if content_length > settings.FILE_UPLOAD_MAX_MEMORY_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = -1

try:
    from settings_local import *
except:
    pass

try:
    modify_globals(globals())
except:
    pass

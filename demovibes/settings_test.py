from settings import *

INSTALLED_APPS = list(INSTALLED_APPS)
INSTALLED_APPS.remove("south")

UWSGI_EVENT_SERVER = None

DISABLE_AJAX = True

MEDIA_URL = 'http://www.scenemusic.net/static/'

CACHE_BACKEND = 'memcached://127.0.0.1:11211/'

KEY_PREFIX = "TT"
#CACHES = {
#    'default': {
#        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
#    }
#}

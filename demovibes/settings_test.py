from settings import *

INSTALLED_APPS = list(INSTALLED_APPS)
INSTALLED_APPS.remove("south")

DISABLE_AJAX = True

MEDIA_URL = 'http://www.scenemusic.net/static/'

CACHE_BACKEND = 'memcached://127.0.0.1:11211/'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

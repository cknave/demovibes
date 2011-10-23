from django.conf.urls.defaults import *
from piston.resource import Resource
from api.handlers import SongHandler, AuthQueueHandler, AuthUserHandler, ArtistHandler, AuthProfile
from piston.doc import documentation_view
from piston.authentication import HttpBasicAuthentication

auth = HttpBasicAuthentication(realm="My Realm")
ad = { 'authentication': auth }

profile_handler = Resource(AuthProfile, **ad)
song_handler = Resource(SongHandler)
queue_handler = Resource(AuthQueueHandler, **ad)
user_handler = Resource(AuthUserHandler, **ad)
artist_handler = Resource(ArtistHandler)

urlpatterns = patterns('',
   url(r'^song/(?P<song_id>\d+)/', song_handler, name="api_song_handler"),
   url(r'^artist/(?P<artist_id>\d+)/', artist_handler, name="api_artist_handler"),
   url(r'^queue/', queue_handler, name="api_queue_handler2"),
   url(r'^profile/', profile_handler, name="api_profile_handler"),
   url(r'^queue/(?P<queueid>\d+)/', queue_handler, name="api_queue_handler"),
   url(r'^user/(?P<username>\w+)/', user_handler, name="api_user_handler"),
   url(r'^$', documentation_view, name="api_docs"),
)

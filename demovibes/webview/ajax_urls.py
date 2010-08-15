from django.conf.urls.defaults import *
from demovibes.webview.models import *

urlpatterns = patterns('',
    (r'^ping/(?P<event_id>\d+)/$',   'demovibes.webview.ajax_views.ping'),
    (r'^monitor/(?P<event_id>\d+)/$',   'demovibes.webview.ajax_views.monitor'),
    (r'^nowplaying/$',          'demovibes.webview.ajax_views.nowplaying'),
    (r'^queue/$',               'demovibes.webview.ajax_views.queue'),
    (r'^history/$',             'demovibes.webview.ajax_views.history'),
    url(r'^oneliner/$',            'demovibes.webview.ajax_views.oneliner', name="dv-ax-oneliner"),
    (r'song/(?P<song_id>\d+)/queue/',   'demovibes.webview.views.addqueue'),
    url(r'^tags/$',            'demovibes.webview.ajax_views.get_tags', name="dv-ax-taglist"),
    (r'a_queue_(?P<song_id>\d+)/$',        'demovibes.webview.ajax_views.songupdate'),
    (r'words/(?P<prefix>\w+)/$',        'demovibes.webview.ajax_views.words'),
    url(r'oneliner_submit/$',                'demovibes.webview.ajax_views.oneliner_submit', name = "dv-ax-oneliner_submit"),
)

from django.conf.urls.defaults import *
from demovibes.webview.models import *
from django.views.generic.list_detail import object_detail, object_list
from demovibes.webview.common import cache_output #needs caching on generic stuff too..

song_dict = {
    'queryset': Song.objects.all(),
    'mimetype': "application/xml",
    'template_name': 'webview/xml/song.xml',
}

stream_dict = {
    'queryset' : RadioStream.objects.all(),
    'mimetype': "application/xml",
    'template_name': 'webview/xml/streams.xml',
}

compilation_dict = {
    'queryset': Compilation.objects.all(),
    'mimetype': "application/xml",
    'template_name': 'webview/xml/compilation.xml',
}

artist_dict = {
    'queryset': Artist.objects.all(),
    'mimetype': "application/xml",
    'template_name': 'webview/xml/artist.xml',
}

group_dict = {
    'queryset': Group.objects.all(),
    'mimetype': "application/xml",
    'template_name': 'webview/xml/group.xml',
}

def cached_object_list(*args, **kwargs):
    return object_list(*args, **kwargs)

def cached_object_detail(*args, **kwargs):
    return object_detail(*args, **kwargs)

urlpatterns = patterns('',
    (r'^queue/$',  	                'demovibes.webview.xml_views.queue'),
    (r'^oneliner/$',  	            'demovibes.webview.xml_views.oneliner'),
    (r'^online/$',  	            'demovibes.webview.xml_views.online'),
    (r'^song/(?P<object_id>\d+)/$', cached_object_detail , song_dict),
    (r'^compilation/(?P<object_id>\d+)/$', cached_object_detail , compilation_dict),
    (r'^group/(?P<object_id>\d+)/$', cached_object_detail , group_dict), 
    (r'^artist/(?P<object_id>\d+)/$', cached_object_detail, artist_dict),     
    (r'^streams/$',                 cached_object_list, stream_dict),
    #(r'^artist/$', 	'demovibes.webview.xml_views.artist'),
    #(r'^user/$',  	'demovibes.webview.xml_views.user'),
)

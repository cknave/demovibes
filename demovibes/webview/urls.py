from django.conf.urls.defaults import *
from demovibes.webview.models import *
from django.conf import settings
import djangojinja2        
        
song_dict = {
    'queryset': Song.objects.select_related(depth=1).all(),
    'extra_context': {  'a_test' : "True", 'vote_range': [1, 2, 3, 4, 5]}, 
    'template_loader': djangojinja2._jinja_env,
}

oneliner_dict = {
    'queryset': Oneliner.objects.all(),
    'template_loader': djangojinja2._jinja_env,
}

artist_dict = {
    'queryset': Artist.objects.filter(status="A"),
    'template_loader': djangojinja2._jinja_env,
}

"""
Access any artist object.
"""
artist_a_dict = {
    'queryset': Artist.objects.all(),
    'template_loader': djangojinja2._jinja_env,
}

group_dict = {
    'queryset': Group.objects.filter(status="A"),
    'template_loader': djangojinja2._jinja_env,
}

"""
Access any group object.
"""
group_a_dict = {
    'queryset': Group.objects.all(),
    'template_loader': djangojinja2._jinja_env,
}

"""
Shows all active lables in the system
"""
labels_all_dict = {
    'queryset': Label.objects.filter(status="A"),
    'template_loader': djangojinja2._jinja_env,
}

"""
Queries pending labels, needs to be all or pending wont show
"""
labels_a_dict = {
    'queryset': Label.objects.all(),
    'template_loader': djangojinja2._jinja_env,
}

news_dict = {
    'queryset': News.objects.all(),
    'template_loader': djangojinja2._jinja_env,
}

comp_dict = {
    'queryset': Compilation.objects.filter(status="A"),
    'template_loader': djangojinja2._jinja_env,
}

streams_dict_txt = {
    'queryset': RadioStream.objects.filter(active=True, streamtype = 'M'),
    'template_loader': djangojinja2._jinja_env,
}
streams_dict = {
    'queryset': RadioStream.objects.filter(active=True).order_by('name'),
    'template_name' : "webview/streams.html",
    'template_loader': djangojinja2._jinja_env,
}

"""
Retreive all FAQ Questions marked as 'Active'
"""
faq_dict = {
    'queryset': Faq.objects.filter(active=True),
    'template_loader': djangojinja2._jinja_env,
}

platforms = {
    'queryset' : SongPlatform.objects.all(),
    'template_loader': djangojinja2._jinja_env,
    #'paginate_by': 500,
}

sources = {
    'queryset' : SongType.objects.all(),
    'template_loader': djangojinja2._jinja_env,
    #'paginate_by': 500,
}

urlpatterns = patterns('',
    # First, some generic 'site' areas commonly found on any site
    url(r'^about/$',                              'demovibes.webview.views.site_about', name = "dv-about"),

    url(r'^inbox/$',                               'demovibes.webview.views.inbox', name = "dv-inbox"),
    url(r'^inbox/(?P<pm_id>\d+)/$',                'demovibes.webview.views.read_pm', name = "dv-read_pm"),
    url(r'^inbox/send/$',                          'demovibes.webview.views.send_pm', name = "dv-send_pm"),
    
    url(r'^play/$',                                'django.views.generic.simple.direct_to_template', \
                { 'template':'webview/radioplay.html'}, name = "dv-play_stream"),
    url(r'^$',                                     'django.views.generic.list_detail.object_list',     news_dict, name = "dv-root"),
    url(r'^streams/streams.txt$',                  'django.views.generic.list_detail.object_list',     streams_dict_txt, name = "dv-streams.txt"),
    url(r'^streams/$',                             'django.views.generic.list_detail.object_list',     streams_dict, name = "dv-streams"),
    url(r'^oneliner/$',                            'django.views.generic.list_detail.object_list', \
                dict(oneliner_dict, paginate_by=settings.PAGINATE), name = "dv-oneliner"),
    url(r'^search/$',                              'demovibes.webview.views.search', name = "dv-search"),
    url(r'^recent/$',                              'demovibes.webview.views.show_approvals', name = "dv-recent"),
    url(r'^platform/(?P<object_id>\d+)/$',         'django.views.generic.list_detail.object_detail', platforms, name = "dv-platform"),
    url(r'^platforms/$',                           'django.views.generic.list_detail.object_list', platforms, name = "dv-platforms"),
    
    url(r'^sources/$',                           'django.views.generic.list_detail.object_list', sources, name = "dv-sources"),
    url(r'^source/(?P<object_id>\d+)/$',         'django.views.generic.list_detail.object_detail', sources, name = "dv-source"),
    
    #Song views
    url(r'^songs/$',                               'django.views.generic.list_detail.object_list', \
                dict(song_dict, extra_context = { 'al' : alphalist }), name = "dv-songs"),
    url(r'^songs/(?P<letter>.)/$',                 'demovibes.webview.views.list_songs', name = "dv-songs_letter"),
    url(r'^song/(?P<song_id>\d+)/$',             'demovibes.webview.views.list_song',   name = "dv-song"),
    url(r'^song/(?P<song_id>\d+)/comments/$',      'demovibes.webview.views.list_song_comments', name = "dv-song_comment"),
    url(r'^song/(?P<song_id>\d+)/votes/$',         'demovibes.webview.views.list_song_votes', name = "dv-song_votes"),
    url(r'^song/(?P<song_id>\d+)/queue_history/$', 'demovibes.webview.views.list_song_history', name = "dv-song_history"),
    
    url(r'^groups/$',                             'django.views.generic.list_detail.object_list', \
                dict(group_dict, extra_context = { 'al' : alphalist }), name = "dv-groups"),
    url(r'^groups/(?P<letter>.)/$',               'demovibes.webview.views.list_groups', name = "dv-groups_letter"),
    url(r'^group/(?P<object_id>\d+)/$',            'django.views.generic.list_detail.object_detail',       group_a_dict, name = "dv-group"),

    url(r'^statistics/(?P<stattype>\w+)/$',                 'demovibes.webview.views.song_statistics', name = "dv-stats"),

    url(r'^artists/$',                             'django.views.generic.list_detail.object_list', \
            dict(artist_dict, extra_context = { 'al' : alphalist }), name = "dv-artists"),
    url(r'^artists/(?P<letter>.)/$',               'demovibes.webview.views.list_artists', name = "dv-artists_letter"),
    url(r'^artist/(?P<object_id>\d+)/$',           'django.views.generic.list_detail.object_detail',       artist_a_dict, name = "dv-artist"),
    url(r'^artist/(?P<artist_id>\d+)/upload/$',    'demovibes.webview.views.upload_song', name = "dv-upload"),

    # New voting system, works differently so contains its own views. This is for URL voting. A
    # Vote can be passed via URL, such as a 3rd party app, in the form of:
    # http://site/demovibes/song/12/vote/1/
    url(r'^song/(?P<song_id>\d+)/vote/(?P<user_rating>\d+)/$',          'demovibes.webview.views.set_rating_autovote', name = "dv-vote-autovote"),

    # We also want to keep traditional voting support, for non-playing songs
    url(r'^song/(?P<song_id>\d+)/vote/$',          'demovibes.webview.views.set_rating', name = "dv-vote"),

    # Add support for displaying all compilations
    url(r'^compilations/$',                             'django.views.generic.list_detail.object_list', \
                dict(comp_dict, extra_context = { 'al' : alphalist }), name = "dv-compilations"),
     url(r'^compilations/(?P<letter>.)/$',               'demovibes.webview.views.list_compilations', name = "dv-compilations_letter"),

    url(r'^user/$',                                'demovibes.webview.views.my_profile', name = "dv-my_profile"),
    url(r'^online/$',                              'demovibes.webview.views.users_online', name = "dv-users_online"),
    url(r'^user/(?P<user>\w+)/$',                  'demovibes.webview.views.view_profile', name = "dv-profile"),
    url(r'^user/(?P<user>\w+)/favorites/$',        'demovibes.webview.views.view_user_favs', name = "dv-user-favs"),
    url(r'^queue/$',                               'demovibes.webview.views.list_queue', name = "dv-queue"),
    url(r'^song/(?P<song_id>\d+)/queue/$',         'demovibes.webview.views.addqueue', name = "dv-add_queue"),
    url(r'^comment/add/(?P<song_id>\d+)/$',        'demovibes.webview.views.addcomment', name = "dv-addcomment"),
    url(r'^tags/$',                                'demovibes.webview.views.tag_cloud', name = "dv-tagcloud"),
    url(r'^tags/(?P<tag>[^/]+)/$',                 'demovibes.webview.views.tag_detail', name = "dv-tagdetail"),
    url(r'^song/(?P<song_id>\d+)/tags/$',           'demovibes.webview.views.tag_edit', name = "dv-songtags"),
    url(r'^favorites/add/(?P<id>\d+)/$',           'demovibes.webview.views.add_favorite', name = "dv-add_fav"),
    url(r'^favorites/$',                           'demovibes.webview.views.list_favorites', name = "dv-favorites"),
    url(r'^favorites/del/(?P<id>\d+)/$',           'demovibes.webview.views.del_favorite', name = "dv-del_fav"),
    url(r'^uploaded_songs/$',                      'demovibes.webview.views.activate_upload', name = "dv-uploads"),
    url(r'^oneliner/submit/$',                     'demovibes.webview.views.oneliner_submit', name = "dv-oneliner_submit"),
    (r'^ajax/',                                    include('demovibes.webview.ajax_urls')),
    (r'^xml/',                                     include('demovibes.webview.xml_urls')),

    # Compilation Views
    url(r'^compilation/(?P<comp_id>\d+)/$',             'demovibes.webview.views.view_compilation',       name = "dv-compilation"),

    # Creation URL's for users to make new stuff
    url(r'^artist/create/$',                    'demovibes.webview.views.create_artist', name = "dv-createartist"),
    url(r'^new_artists/$',                      'demovibes.webview.views.activate_artists', name = "dv-newartists"),
    url(r'^group/create/$',                     'demovibes.webview.views.create_group', name = "dv-creategroup"),
    url(r'^new_groups/$',                       'demovibes.webview.views.activate_groups', name = "dv-newgroups"),
    
    # Production label URL's (Labels/Producers Specific)
    url(r'^labels/$',                             'django.views.generic.list_detail.object_list', \
                dict(labels_all_dict, extra_context = { 'al' : alphalist }), name = "dv-labels"),
    url(r'^label/(?P<object_id>\d+)/$',            'django.views.generic.list_detail.object_detail',       labels_a_dict, name = "dv-label"),
    url(r'^labels/(?P<letter>.)/$',               'demovibes.webview.views.list_labels', name = "dv-labels_letter"),
    url(r'^label/create/$',                    'demovibes.webview.views.create_label', name = "dv-createlabel"),
    url(r'^new_labels/$',                      'demovibes.webview.views.activate_labels', name = "dv-newlabels"),
    
    # Link Management
    url(r'^links/(?P<slug>[-\w]+)/$',          'demovibes.webview.views.link_category', name = "dv-linkcategory"),
    url(r'^link/create/$',                    'demovibes.webview.views.link_create', name = "dv-createlink"),
    url(r'^link/pending/$',                   'demovibes.webview.views.activate_links', name = "dv-newlinks"),
    url(r'^links/$',                           'demovibes.webview.views.site_links', name = "dv-links"), # View existing Links
    
    # FAQ System
    url(r'^faq/$',                                'django.views.generic.list_detail.object_list', faq_dict, name = "dv-faq"), # Generic FAQ System (All active Questions)
    url(r'^faq/(?P<object_id>\d+)/$',           'django.views.generic.list_detail.object_detail', faq_dict, name = "dv-faqitem"),
    
    # Statistics & Cache stuff
    url(r'^status/cache/$',                    'demovibes.webview.views.memcached_status', name = "dv-memcached"), # Show memcached status

)

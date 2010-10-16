from demovibes.webview.models import *
from demovibes.webview.common import *
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
import socket

from tagging.models import Tag

from django.template import RequestContext
from django.conf import settings
from django.db.models import Q
import time, datetime
from django.core.cache import cache
import j2shim

use_eventful = getattr(settings, 'USE_EVENTFUL', False)

#For updating last_active field before sending to (external?) event handler
def ping(request, event_id):
    if request.user.is_authenticated():
        key = "uonli_%s" % request.user.id
        get = cache.get(key)
        if not get:
            P = get_profile(request.user)
            P.last_activity = datetime.datetime.now()
            P.save()
            cache.set(key, "1", 100)
    return HttpResponseRedirect("/demovibes/ajax/monitor/%s/" % event_id)

def monitor(request, event_id):
    for x in range(120):
        R = AjaxEvent.objects.filter(id__gt=event_id).order_by('id')
        if R:
            entries = list()
            for event in R:
                if event.user == None or event.user == request.user:
                    if not str(event.event) in entries:
                        entries.append(str(event.event))
            ajaxid = R.order_by('-id')[0].id
            return render_to_response('webview/js/manager.html', \
                { 'events' : entries, 'id' : ajaxid },  context_instance=RequestContext(request))
        time.sleep(2)
    return HttpResponse("")


@cache_control(must_revalidate=True, max_age=10)
def nowplaying(request):
    song = Queue.objects.select_related(depth=2).filter(played=True).order_by('-time_played')[0]
    return j2shim.r2r('webview/js/now_playing.html', { 'now_playing' : song, 'user':request.user },  request)

@cache_control(must_revalidate=True, max_age=30)
def history(request):
    return HttpResponse(get_history())

@cache_control(must_revalidate=True, max_age=30)
def queue(request):
    return HttpResponse(get_queue())

def oneliner_submit(request):
    if not request.user.is_authenticated():
        return HttpResponse("NoAuth")
    message = request.POST['Line'].strip()
    add_oneliner(request.user, message)
    return HttpResponse("OK")

def get_tags(request):
    q = request.GET['q']
    if q:
        l = []
        t = Tag.objects.filter(name__istartswith=q)[:20]
        for tag in t:
            if tag.items.count():
                l.append("%s - %s song(s)" % (tag.name, tag.items.count()))
        return HttpResponse('\n'.join(l))
    return HttpResponse()

@cache_control(must_revalidate=True, max_age=30)
def oneliner(request):
    return HttpResponse(get_oneliner())

@cache_control(must_revalidate=True, max_age=30)
def songupdate(request, song_id):
    song = Song.objects.get(id=song_id)
    return j2shim.r2r('webview/js/generic.html', { 
        'song' : song,
        'event' : "a_queue_%i" % song.id,
        'template' : 'webview/t/songlist_span.html',
        },  request)

def words(request, prefix): 
    extrawords=['boobies','boobietrap','nectarine']; 
    words= [a.username+"" for a in User.objects.filter(username__istartswith=prefix)];
    words.extend([a.handle+"" for a in Artist.objects.filter(handle__istartswith=prefix)]);
    words.extend([a.name+"" for a in Artist.objects.filter(name__istartswith=prefix)]);
    words.extend([a.name+"" for a in Group.objects.filter(name__istartswith=prefix)]);
    words.extend([a for a in extrawords if a.lower().startswith(prefix.lower())]);
    return HttpResponse(",".join(words));

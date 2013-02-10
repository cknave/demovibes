from demovibes.webview.models import *
from demovibes.webview.common import *
from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.cache import cache_page
from django.shortcuts import render_to_response

from mybaseview import MyBaseView

from django.utils import simplejson

from haystack.query import SearchQuerySet

from tagging.models import Tag

from django.template import RequestContext
from django.conf import settings
import time, datetime
from django.core.cache import cache
import j2shim
import re
import hashlib

idlist = re.compile(r'^(\d+,)+\d+$')

use_eventful = getattr(settings, 'USE_EVENTFUL', False)
UWSGI_ID_SECRET = getattr(settings, 'UWSGI_ID_SECRET', False)

class AjaxView(MyBaseView):
    basetemplate = "webview/js/"

@cache_page(60*60*24)
@cache_control(max_age=3600*24)
def smileys(request):
    s = simplejson.dumps(settings.SMILEYS)
    return HttpResponse(s, "application/json")

class LicenseView(AjaxView):
    template = "license.html"

    def set_context(self):
        id = self.kwargs.get("id")
        lic = SongLicense.objects.get(id=id)
        return {'license': lic}

def songinfo(request):
    def makeinfo(song):
        return {"title": song.title, "artists": song.artist(), "id": song.id, "url": song.get_absolute_url(), "slength": song.get_songlength()}
    songid = request.REQUEST.get("q", "").strip()
    if not songid:
        return HttpResponse('{"error": "Empty input"}')
    if songid.isdigit():
        try:
            S = Song.objects.get(id=songid)
            result = [makeinfo(S)]
            return HttpResponse(simplejson.dumps(result))
        except:
            return HttpResponse('{"error": "No song by that ID"}')

    if idlist.match(songid):
            num = songid.split(",")
            res = []
            for x in num:
                S = Song.objects.get(id=x)
                res.append(makeinfo(S))
            return HttpResponse(simplejson.dumps(res))


    SL = SearchQuerySet().auto_query(songid).models(Song).load_all()[:20]
    if not SL:
        return HttpResponse('{"error": "No results found"}')
    data = []
    for S in SL:
        data.append(makeinfo(S.object))
    return HttpResponse(simplejson.dumps(data))

#For updating last_active field before sending to (external?) event handler
def ping(request, event_id):
    if getattr(settings, "DISABLE_AJAX", False):
        raise
    GET_UID = ""
    if request.user.is_authenticated():
        key = "uonli_%s" % request.user.id
        GET_UID = "?uid=%s" % request.user.id
        if UWSGI_ID_SECRET:
            hash = hashlib.sha1("%s.%s" % (request.user.id, UWSGI_ID_SECRET)).hexdigest()
            GET_UID = GET_UID + "&sign=" + hash
        get = cache.get(key)
        if not get:
            P = get_profile(request.user)
            P.last_ip = request.META["REMOTE_ADDR"]
            P.last_activity = datetime.datetime.now()
            P.set_flag_from_ip(request.META.get('REMOTE_ADDR'))
            P.save()
            cache.set(key, "1", 100)
    return HttpResponseRedirect("/demovibes/ajax/monitor/%s/%s" % (event_id, GET_UID))

def monitor(request, event_id):
    for x in range(30):
        R = AjaxEvent.objects.filter(id__gt=event_id).order_by('id')
        if R:
            entries = list()
            for event in R:
                if event.user == None or event.user == request.user:
                    if not str(event.event) in entries:
                        entries.append(str(event.event))
            ajaxid = R.order_by('-id')[0].id + 1
            return render_to_response('webview/js/manager.html', \
                { 'events' : entries, 'id' : ajaxid },  context_instance=RequestContext(request))
        time.sleep(1)
    return HttpResponse("")


@cache_control(must_revalidate=True, max_age=10)
def nowplaying(request):
    song = get_now_playing_song()
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
    q = request.GET.get('q')
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
    return HttpResponse("""<span style="display:none">l</span>
                <img class="song_tail" src="%slock.png" title="Locked" alt="Locked"/>""" %
                settings.MEDIA_URL)

    return j2shim.r2r('webview/js/generic.html', {
        'song' : song,
        'event' : "a_queue_%i" % song.id,
        'template' : 'webview/t/songlist_span.html',
        },  request)

def words(request, prefix):
    extrawords = ['boobies', 'boobietrap', 'nectarine']
    words = [a.user.username for a in Userprofile.objects.filter(user__username__istartswith = prefix).order_by("-last_activity")[:20] ]
    words.extend( [a.handle for a in Artist.objects.filter(handle__istartswith = prefix)[:20] ] )
    words.extend( [a.name for a in Group.objects.filter(name__istartswith = prefix)[:20] ] )
    words.extend( [a for a in extrawords if a.lower().startswith( prefix.lower() ) ] )
    return HttpResponse(",".join(words))

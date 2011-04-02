from demovibes.webview.models import *
from demovibes.webview.common import get_now_playing_song
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from mybaseview import BaseView

class XMLView(BaseView):
    mimetype = "application/xml"
    basetemplate = 'webview/xml/'

def queue(request):
    try :
        now_playing = get_now_playing_song()
        if now_playing:
            history = Queue.objects.select_related(depth=2).filter(played=True).filter(id__gt=now_playing.id - 50).order_by('-id')[1:21]
        else:
            history = Queue.objects.select_related(depth=2).filter(played=True).order_by('-id')[1:21]
    except IndexError:
        history = []
    queue = Queue.objects.select_related(depth=2).filter(played=False).order_by('id')
    return render_to_response('webview/xml/queue.xml', \
        {'now_playing': now_playing, 'history': history, 'queue': queue}, \
        context_instance=RequestContext(request), mimetype = "application/xml")

def user(request, username):
    user = get_object_or_404(User, username = username)
    if user.get_profile().visible_to != "A":
        user = None
    return render_to_response('webview/xml/user.xml', \
        {'user' : user}, \
        context_instance=RequestContext(request), mimetype = "application/xml")

def oneliner(request):
    try:
        oneliner_data = Oneliner.objects.select_related(depth=1).order_by('-id')[:20]
    except:
        return "Invalid Oneliner Data"

    return render_to_response('webview/xml/oneliner.xml', \
        {'oneliner_data' : oneliner_data}, \
        context_instance=RequestContext(request), mimetype = "application/xml")

def online(request):
    try:
        timefrom = datetime.datetime.now() - datetime.timedelta(minutes=5)
        online_data = Userprofile.objects.filter(last_activity__gt=timefrom).order_by('user__username')
    #online_data = Userprofile.objects.select_related(depth=2).filter(last_activity__gt=timefrom).order_by('user__username')[1:50]
    except:
        return "Invalid Online Data"

    return render_to_response('webview/xml/online.xml', \
        {'online_data' : online_data}, \
        context_instance=RequestContext(request), mimetype = "application/xml")

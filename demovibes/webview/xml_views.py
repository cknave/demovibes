from demovibes.webview.models import *
from demovibes.webview.common import cache_output
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.conf import settings

def queue(request):
	try :
		now_playing = Queue.objects.select_related(depth=2).filter(played=True).order_by('-id')[0]
	except IndexError:
		now_playing = ""
	history = Queue.objects.select_related(depth=2).filter(played=True).order_by('-id')[1:21]
	queue = Queue.objects.select_related(depth=2).filter(played=False).order_by('id')
	return render_to_response('webview/xml/queue.xml', \
		{'now_playing': now_playing, 'history': history, 'queue': queue}, \
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

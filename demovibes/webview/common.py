import time
from webview import models
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render_to_response
from django.template import Context, Template
from django.template.loader import get_template
from django.conf import settings
import logging
import socket
import datetime
import j2shim

def play_queued(queue):
    queue.song.times_played = queue.song.times_played + 1
    queue.song.save()
    queue.time_played=datetime.datetime.now()
    queue.played = True
    queue.save()
    temp = get_now_playing(True)
    temp = get_history(True)
    temp = get_queue(True)
    models.add_event(event="queue")
    models.add_event(event="history")
    models.add_event(event="nowplaying")
    

# This function should both make cake, and eat it
def queue_song(song, user, event = True, force = False):
    sl = settings.SONG_LOCK_TIME
    Q = False
    time = datetime.timedelta(hours = sl['hours'], days = sl['days'], minutes = sl['minutes'])
    result = True
    models.Queue.objects.lock(models.Song, models.User, models.AjaxEvent)
    if not force:
        requests = models.Queue.objects.filter(played=False, requested_by = user).count()
        if requests >= settings.SONGS_IN_QUEUE:
            models.add_event(event='eval:alert("You have reached your queue limit! Please wait for your requests to play.");', user = user)
            result = False
        if result and song.is_locked():
            result = False
    if result:
        song.locked_until = datetime.datetime.now() + time
        song.save()
        Q = models.Queue(song=song, requested_by=user, played = False)
        Q.save()
    models.Queue.objects.unlock()
    if result:
        Q.eta = Q.get_eta()
        Q.save()
        models.add_event(event='a_queue_%i' % song.id)
        if event:
            bla = get_queue(True) # generate new queue cached object
            models.add_event(event='queue')
    return Q


def get_now_playing_song(create_new=False):
    queueobj = cache.get("nowplaysong")
    if not queueobj or create_new:
        try:
            queueobj = models.Queue.objects.select_related(depth=3).filter(played=True).order_by('-time_played')[0]
        except:
            return False
        cache.set("nowplaysong", queueobj, 300)
    return queueobj

def get_now_playing(create_new=False):
    logging.debug("Getting now playing")
    key = "nnowplaying"
    
    try:
        songtype = get_now_playing_song(create_new)
        song = songtype.song
    except:
        return ""
       
    R = cache.get(key)
    if not R or create_new:
        comps = models.Compilation.objects.filter(songs__id = song.id)
        R = j2shim.r2s('webview/t/now_playing_song.html', { 'now_playing' : songtype, 'comps' : comps })
        cache.set(key, R, 300)
        logging.debug("Now playing generated")
    R = R % songtype.timeleft()
    return R

def get_history(create_new=False):
    key = "nhistory"
    logging.debug("Getting history cache")
    R = cache.get(key)
    if not R or create_new:
        logging.info("No existing cache for history, making new one")
        history = models.Queue.objects.select_related(depth=3).filter(played=True).order_by('-time_played')[1:21]
        R = j2shim.r2s('webview/js/history.html', { 'history' : history })
        cache.set(key, R, 300)
        logging.debug("Cache generated")
    return R

def get_oneliner(create_new=False):
    key = "noneliner"
    logging.debug("Getting oneliner cache")
    R = cache.get(key)
    if not R or create_new:
        logging.info("No existing cache for oneliner, making new one")
        lines = getattr(settings, 'ONELINER', 10)
        oneliner = models.Oneliner.objects.select_related(depth=2).order_by('-id')[:lines]
        R = j2shim.r2s('webview/js/oneliner.html', { 'oneliner' : oneliner })
        cache.set(key, R, 600)
        logging.debug("Cache generated")
    return R

def get_queue(create_new=False):
    key = "nqueue"
    logging.debug("Getting cache for queue")
    R = cache.get(key)
    if not R or create_new:
        logging.info("No existing cache for queue, making new one")
        queue = models.Queue.objects.select_related(depth=2).filter(played=False).order_by('id')
        R = j2shim.r2s("webview/js/queue.html", { 'queue' : queue })
        cache.set(key, R, 300)
        logging.debug("Cache generated")
    return R

def get_profile(user):
    """
    Get a user's profile.

    Tries to get a user's profile, and create it if it doesn't exist.
    """
    try:
        profile = user.get_profile()
    except:
        profile = models.Userprofile(user = user)
        profile.save()
    return profile

def get_latest_event():
    use_eventful = getattr(settings, 'USE_EVENTFUL', False)
    if use_eventful:
        host = getattr(settings, 'EVENTFUL_HOST', "127.0.0.1")
        port = getattr(settings, 'EVENTFUL_PORT', 9911)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            s.connect((host, port))
            s.send("event::")
            result = s.recv(1024)
        except socket.timeout:
            return 0
        return result.strip()
    else:
        try:
            return models.AjaxEvent.objects.order_by('-id')[0].id
        except:
            return 0

def log_debug(area, text, level=1):
    settings_level = getattr(settings, 'DEBUGLEVEL', 0)
    settings_debug = getattr(settings, 'DEBUG')
    settings_file = getattr(settings, 'DEBUGFILE', "/tmp/django-error.log")
    if settings_debug and level <= settings_level:
        F = open(settings_file, "a")
        F.write("(%s) <%s:%s> %s\n" % (time.strftime("%d/%b/%Y %H:%M:%S", time.localtime()), area, level, text))
        F.close()


def get_event_key(key):
    event = get_latest_event()
    return "%sevent%s" % (key, event)
    
# Not perfect, borks if I add () to decorator (or arguments..)
# Tried moving logic to call and def a wrapper there, but django somehow didn't like that
#
# Code will try to find an "event" value in the GET part of the url. If it can't find it,
# the current event number is collected from database.
class cache_output(object):
    
    def __init__(self, f):
        self.f = f
        self.n = f.__name__
        self.s = 60*5 # default cache time in seconds
        
    def __call__(self, *args, **kwargs):
        try:
            try:
                path = args[0].path
            except:
                path = self.n
            try:
                event = args[0].GET['event']
            except: # no event get string found
                event = get_latest_event()
            key = "%s.%s" % (path, event)
            value = cache.get(key)
            if not value:
                value = self.f(*args, **kwargs)
                cache.set(key, value, self.s)
        except:
            value = self.f(*args, **kwargs)
        return value

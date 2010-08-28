#!/usr/bin/env python
from django.core.management import setup_environ
import settings
setup_environ(settings)
import logging
import os
import sys
from webview.models import *
from webview import dscan
#problem: I don't rally know when to convert to fsencoding :D
#problem: file fild might need to be extended to something that makes sense (255)
#problem: can't find logger

L = logging.getLogger('DbFix')
fsenc = sys.getfilesystemencoding()

media_dir = getattr(settings, 'MEDIA_ROOT', False)
if not media_dir:
    print "set MEDIA_ROOT"
    exit

songs = Song.objects.filter(replay_gain=0)

for song in songs:
    F = song.file.path
    if not os.path.isfile(F):
        dir, prefix = os.path.split(song.file.path)
        found_one_match = False
        
        for root, dirs, files in os.walk(media_dir):
            if found_one_match:
                break
            for filename in files:
                path = os.path.join(root, filename)
                if path.startswith(F):
                    found_one_match = True
                    break

        if found_one_match:
            print "REPLACE %s -> %s" % (F, path)
            #problem right here: it works but database will contain absolute path
            song.file = path.lstrip(media_dir)
            song.save()
        else:
            print "can't find replacement for %s" % F
            #L.error("can't find %s or replacement " % prefix) 
            song.status = 'K' # K = Kaput = file missing...
            song.save()
    if os.path.isfile(song.file.path):
        print "scanning", song, song.file.path
        
        r = song.set_song_data()
        
        if not r:
            song.status = "K"

        song.save()

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
L = logging.getLogger('dscan')
fsenc = sys.getfilesystemencoding()

media_dir = getattr(settings, 'MEDIA_URL', False)
if not media_dir:
    print "set MEDIA_URL"
    exit

songs = Song.objects.filter(replay_gain=0)
#songs = Song.objects.all()
for song in songs:
    if not os.path.isfile(song.file.path):
        dir, prefix = os.path.split(song.file.path.encode(fsenc))
        found_one_match = False
        for root, dirs, files in os.walk(media_dir):
            for file in files:
                if file.startswith(prefix):
                    if found_one_match:
                        found_one_match = False
                        break
                    new_file = file
                    found_one_match = True
            if found_one_match:
                print "REPLACE %s -> %s" % file % new_file
                #problem right here: it works but database will contain absolute path
                song.file = dir + '/' + new_file
                song.save()
            else:
                print "can't replacement for %s" % prefix
                #L.error("can't find %s or replacement " % prefix) 
                song.status = 'K' # K = Kaput = file missing...
                song.save()
        
    print "scanning", song, song.file.path
    df = dscan.ScanFile(song.file.path)
    if df.readable:
        song.song_length = df.length
        song.replay_gain = df.replaygain()
        song.save()
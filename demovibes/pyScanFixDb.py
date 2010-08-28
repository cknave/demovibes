#!/usr/bin/env python
import logging
import os
import sys
#problem: I don't rally know when to convert to fsencoding :D
#problem: file fild might need to be extended to something that makes sense (255)
#problem: can't find logger

import optparse
parser = optparse.OptionParser()
parser.add_option("-a", "--all", action="store_true", default=False, dest="all", help="Scan all songs")
parser.add_option("-d", "--debug", action="store_true", default=False, dest="debug", help="Debug output")
parser.add_option("--logfile", dest="logfile", default=None, metavar="FILE", help="Also write log to logfile")
parser.add_option("-s", "--status", dest="status", default="K", metavar="STATUS", help="Set borked files to given status. Default: K")
(options, args) = parser.parse_args()

#filename=options.logfile

if options.debug:
    logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M', format='[%(asctime)s] %(message)s')
else:
    logging.basicConfig(level=logging.INFO, datefmt='%H:%M', format='[%(asctime)s] %(message)s')

if options.logfile:
    fhandler = logging.FileHandler(options.logfile)
    fhandler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    fhandler.setFormatter(formatter)
    logging.getLogger('').addHandler(fhandler)

from django.core.management import setup_environ
import settings
setup_environ(settings)
from webview.models import *
from webview import dscan

L = logging.getLogger('DbFix')
fsenc = sys.getfilesystemencoding()

media_dir = getattr(settings, 'MEDIA_ROOT', False)
if not media_dir:
    print "set MEDIA_ROOT"
    exit

if options.all:
    songs = Song.objects.all()
else:
    songs = Song.objects.filter(replay_gain=0)

numsongs = songs.count()
currsong = 0

for song in songs:
    currsong += 1
    F = song.file.path.encode(fsenc)
    L.info(u"""(%5d/%5d) Checking %5d : "%s" by "%s" """ % (currsong, numsongs, song.id, song.title, song.artist()))
    
    if not os.path.isfile(F):
        L.debug("Song %s seem to have incomplete path. Trying to fix")
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
            sf = path.replace(media_dir, "", 1).lstrip("/\\")
            L.debug(u"Song %s : Setting path to %s" % (song.id, sf))
            song.file = sf
            song.save()
        else:
            L.warning("can't find %s or replacement " % prefix)
            song.status = options.status
            song.save()
    if os.path.isfile(song.file.path):
        r = song.set_song_data()
        
        if not r:
            L.debug(u"Song #%s - Could not parse file" % song.id)
            song.status = options.status

        song.save()

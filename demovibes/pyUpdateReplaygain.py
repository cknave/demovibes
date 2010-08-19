#!/usr/bin/env python
from django.core.management import setup_environ
import settings
setup_environ(settings)

from webview.models import *
from webview import dscan

songs = Song.objects.filter(replay_gain=0)
#songs = Song.objects.all()
for song in songs:
    print "scanning", song, song.file.path
    df = dscan.ScanFile(song.file.path)
    #might as well set length - scan does a proper scan, not only read header
    song.song_length = df.length
    song.replay_gain = df.replaygain()
    song.save()
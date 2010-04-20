#!/usr/bin/env python
import sys, random, os, getopt

from django.core.management import setup_environ
import settings
setup_environ(settings)
from webview.models import *
from django.contrib.auth.models import User

from string import *

def usage():
	print """Adds an mp3 to the database.

-f <file> 	Path to file
-t <title> 	Title of song
-a <artist> 	Artist (Can be used multiple times)
-C 		Auto add artist if he does not exist.

--status=<char>	Song status. Can be:
		A - Active (Default)
		I - Inactive
		J - Jingle
		V - Needs verification
"""

try:                                
	opts, args = getopt.getopt(sys.argv[1:], "hf:t:a:C", ["help", "status="])
except getopt.GetoptError:
	usage()
	sys.exit(2)

pymad = False

create = False
sl = ""
status = "A"

artists = []

for opt, arg in opts:
	if opt in ("-h", "--help"):
		usage()
		sys.exit()
	elif opt == '-f':
		music = arg
	elif opt == '-t':
		title = arg.strip().capitalize()
	elif opt == '-a':
		artists.append(arg.strip())
	elif opt == '-C':
		create = True
	elif opt == '--status':
		status = arg


if not os.path.exists(music):
	print "File does not exist!"
	sys.exit()

A = []
for artist in artists:
	A1 = Artist.objects.filter(handle=artist)
	if A1:
		A.append(A1[0])
	else:
		if create:
			print "Can not find artist '%s'. Creating.." % artist
			A1 = Artist(handle=artist)
			A1.save()
			A.append(A1)
		else:
			print "Can not find artist '%s'. Exiting." % artist
			sys.exit(1)

S = Song(title=title, file=music, status=status)
if pymad:
	mf = mad.MadFile(music)
	seconds = mf.total_time()/1000
	S.song_length = seconds
	sl = "Song length is %i seconds." % seconds
S.save()
S.artists = A
S.save()

print "Added file '%s' with artist(s) '%s' and title '%s'. %s" % (music, A, title, sl)

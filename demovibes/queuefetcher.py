import sys, random
from datetime import datetime, timedelta
import time
import bitly
from os import popen
import logging, logging.config
from django.core.management import setup_environ
import settings
setup_environ(settings)
from webview.models import Queue, Song
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from webview import common

class song_finder(object):
    songweight = {
        'N' : 1,
        1 : 40,
        2 : 25,
        3 : 10,
        4 : 3,
        5 : 1,
    }

    def __init__(self, djuser = None):
        self.sysenc = sys.getdefaultencoding()
        self.fsenc = sys.getfilesystemencoding()

        self.meta = None
        self.timestamp = None
        self.song = None

        self.log = logging.getLogger("pyAdder")

        if not djuser:
            djuser = getattr(settings, 'DJ_USERNAME', "djrandom")
        try:
            self.dj_user = User.objects.get(username = djuser)
        except:
            print "User (%s) not found! Aborting!" % djuser
            sys.exit(1)

        self.bitly_username = getattr(settings, 'BITLY_USERNAME', False)
        self.bitly_key = getattr(settings, 'BITLY_API_KEY', False)

        self.max_songlength = getattr(settings, 'DJ_MAX_LENGTH', None)
        self.twitter_username = getattr(settings, 'TWITTER_USERNAME', False)
        self.twitter_password = getattr(settings, 'TWITTER_PASSWORD', False)

        self.base_url = self.get_site_url()
        self.init_jt()
        self.weight_table = {
            'N' : 0,
            1 : 0,
            2 : 0,
            3 : 0,
            4 : 0,
            5 : 0
        }

    def findQueued(self):
        """
        Return next queued song, or a random song, or a jingle.
        """
        songs = Queue.objects.filter(played=False, playtime__lte = datetime.datetime.now()).order_by('-priority', 'id')
        if not songs: # Since OR queries have been problematic on production server earlier, we do this hack..
            songs = Queue.objects.filter(played=False, playtime = None).order_by('-priority', 'id')
        if settings.PLAY_JINGLES:
            jingle = self.JingleTime()
            if jingle:
                return jingle
        if songs:
            song = songs[0]
            common.play_queued(song)
            return song.song
        else:
            return self.getRandom()

    def get_metadata(self):
        return self.meta.encode(self.sysenc, 'replace')

    def get_next_song(self):
        """
        Return next song filepath to be played
        """
        if self.timestamp:
            delta = datetime.datetime.now() - self.timestamp
            if delta < timedelta(seconds=3):
                self.log.warning(u"Song '%s' stopped playing after less than 3 seconds for some reason!" % self.meta)
                time.sleep(3)
        self.timestamp = datetime.datetime.now()

        song = self.findQueued()

        self.meta = u"%s - %s" % (song.artist(), song.title)
        self.log.debug("Now playing \"%s\" [ID %s]" % (song.title, song.id))
        self.song = song

        try:
            filepath = song.file.path.encode(self.fsenc)
        except:
            try:
                filepath = song.file.path.encode(self.sysenc)
            except:
                filepath = song.file.path
        self.log.debug("Returning path %s" % filepath)
        return filepath

    def get_site_url(self):
        current_site = Site.objects.get_current()
        protocol = getattr(settings, 'MY_SITE_PROTOCOL', 'http')
        port     = getattr(settings, 'MY_SITE_PORT', '')
        base_url = '%s://%s' % (protocol, current_site.domain)
        if port:
            base_url += ':%s' % port
        return base_url

    def select_random(self, qs):
        nr = qs.count()
        rand = random.randint(0,nr-1)
        entry = qs.order_by('id')[rand]
        return entry

    def getRandom(self):
        query = self.max_songlength and Song.active.filter(song_length__lt = self.max_songlength) or Song.active.all()
        song = self.select_random(query)
        C = 0
        self.log.debug("Trying to find a random song")
        # Try to find a good song that is not locked. Will try up to 10 times.
        while not self.isGoodSong(song) and C < 10:
           self.log.debug("Random %s - song : %s [%s]" % (C, song.title, song.id))
           song = self.select_random(query)
           C += 1
        self.log.debug("Using song %s (%s)" % (song.title, song.id))
        Q = common.queue_song(song, self.dj_user, False, True)
        common.play_queued(Q)
        return song

    def init_jt(self):
        self.jt = {
            'count': 0,
            'timelast': datetime.datetime.now(),
            'max': timedelta(minutes = 30),
            'min': timedelta(minutes = 20)
        }

    def isGoodSong(self, song):
        """Check if song is a good song to play

        Checks if song is locked, and if that voteclass of songs have been played recently.
        Returns true or false
        """
        if song.is_locked() :
            return False

        if song.rating_votes < 5: # Not voted or few votes
            C = 'N'
        else:
            C = int(round(song.rating))
        if self.weight_table[C] >= self.songweight[C]:
            self.weight_table[C] = 0
            return True
        for X in self.weight_table.keys():
            self.weight_table[X] += 1
        return False

    def JingleTime(self):
        jt = self.jt
        if jt['timelast'] + jt['min'] < datetime.datetime.now():
            if jt['count'] >= 10 or jt['max'] + jt['timelast'] < datetime.datetime.now():
                jt['count'] = 0
                jt['timelast'] = datetime.datetime.now()
                S = Song.objects.filter(status='J')
                S = self.select_random(S)
                self.log.debug("JingleTime! ID %s" % S.id)
                return S
        jt['count'] += 1
        self.jt = jt
        return False

    def send_to_twitter(self, song):
        twitter_message = "Now Playing: %s - %s" % (song.artist(), song.title)

        if self.bitly_username and self.bitly_key:
            url = self.base_url + song.get_absolute_url()
            self.log.debug("Bitly : Full URL To Song URL: %s" % url)
            try:
                api = bitly.Api(login=self.bitly_username, apikey=self.bitly_key)
                short_url = api.shorten(url)
                twitter_message += ' - %s' % short_url
            except:
                self.log.warning("Bit.ly failed to shorten url!")

        if self.twitter_username and self.twitter_password:
            self.log.debug("Tweeting: %s" % twitter_message)
            self.tweet(self.twitter_username, self.twitter_password, twitter_message)

    def tweet(self, user, password, message):
        if len(message) < 140:
            url = 'http://twitter.com/statuses/update.xml'
            curl = 'curl --connect-timeout 10 -s -u %s:%s -d status="%s" %s' % (user, password, message, url)
            try:
                popen(curl, 'r')
            except:
                self.log.warning("Failed To Tweet: %s"% message)

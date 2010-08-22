from django.db import models
from django.contrib.auth.models import User
import datetime
import socket
import re
import os.path
from django.conf import settings
from django.core.mail import EmailMessage
#from django.core.urlresolvers import reverse
import mad
import dscan
import logging
import xml.dom.minidom, urllib # Needed for XML processing
from django.core.cache import cache
from django.template.defaultfilters import striptags
from django.contrib.sites.models import Site
from django.template import RequestContext, Context, loader
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy as _

import tagging

#from demovibes.webview.common import get_oneliner, get_now_playing, get_queue, get_history

uwsgi_event_server = getattr(settings, 'UWSGI_EVENT_SERVER', False)

if uwsgi_event_server:
    uwsgi_event_server_http = getattr(settings, 'UWSGI_EVENT_SERVER_HTTP', False)
    try:
        import uwsgi
    except:
        import pickle
        uwsgi_event_server = "HTTP"

def add_event(event, user = None):
    ae = AjaxEvent.objects.create(event = event, user = user)
    if uwsgi_event_server:
        R = AjaxEvent.objects.filter(user__isnull=True).order_by('-id')[:10] #Should have time based limit here..
        R = [(x.id, x.event) for x in R]
        data = (R, ae.id+1)
        if uwsgi_event_server:
            if uwsgi_event_server == "HTTP":
                data = {'data': pickle.dumps(data)}
                data = urllib.urlencode(data)
                logging.debug("Event data via http: %s" % data)
                url = uwsgi_event_server_http or "http://127.0.0.1/demovibes/ajax/monitor/new/"
                r = urllib.urlopen(url, data)
                return r.read()
            else:
                uwsgi.send_uwsgi_message(uwsgi_event_server[0], uwsgi_event_server[1], 33, 17, data, 30)

from managers import *

# Create your models here.

#Used for artist / song listing
alphalist = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '-']

class Group(models.Model):
    STATUS_CHOICES = (
            ('A', 'Active'),
            ('I', 'Inactive'),
            ('D', 'Dupe'),
            ('U', 'Uploaded'),
            ('R', 'Rejected')
        )

    created_by = models.ForeignKey(User,  null = True, blank = True, related_name="group_createdby")
    found_date = models.DateField(verbose_name="Found Date", help_text="Date this group was formed (YYYY-MM-DD)", null=True, blank = True)
    group_icon = models.ImageField(help_text="Group Icon (Shows instead of default icon)", upload_to = 'media/groups/icons', blank = True, null = True)
    group_logo = models.ImageField(help_text="Logo/Pic Of This Group", upload_to = 'media/groups', blank = True, null = True)
    info = models.TextField(blank = True, verbose_name="Group Info", help_text="Additional information on this group. No HTML.")
    last_updated = models.DateTimeField(editable = False, blank = True, null = True)
    name = models.CharField(max_length=80, unique = True, db_index = True, verbose_name="* Name", help_text="The name of this group as you want it to appear.")
    pouetid = models.IntegerField(verbose_name="Pouet ID", help_text="If this group has a Pouet entry, enter the ID number here - See http://www.pouet.net", blank=True, null = True)
    startswith = models.CharField(max_length=1, editable = False, db_index = True)
    status = models.CharField(max_length = 1, choices = STATUS_CHOICES, default = 'A')
    webpage = models.URLField(blank=True, verbose_name="Website", help_text="Add the website address for this group, if one exists.")
    wiki_link = models.URLField(blank=True, help_text="URL to wikipedia entry (if available)")

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        S = self.name[0].lower()
        if not S in alphalist:
            S = '#'
        self.startswith = S
        self.last_updated = datetime.datetime.now()
        return super(Group, self).save(*args, **kwargs)

    @models.permalink
    def get_absolute_url(self):
        return ('dv-group', [str(self.id)])

class GroupVote(models.Model):
    """
    Same voting methods for thumbs up rating, only for groups. AAK
    """
    group = models.ForeignKey(Group)
    vote = models.IntegerField(default=0)
    user = models.ForeignKey(User)
    added = models.DateTimeField(auto_now_add=True)

class Theme(models.Model):
    title = models.CharField(max_length = 20)
    description = models.TextField(blank=True)
    preview = models.ImageField(upload_to='media/theme_preview', blank = True, null = True)
    css = models.CharField(max_length=120)

    def __unicode__(self):
        return self.title

class Userprofile(models.Model):
    VISIBLE_TO = (
        ('A', 'All users'),
        ('R', 'Registrered users'),
        ('N', 'No one')
    )

    def have_artist(self):
        try:
            return self.user.artist
        except:
            return False

    aol_id = models.CharField(blank = True, max_length = 40, verbose_name = "AOL IM", help_text="AOL IM ID, for people to contact you (optional)")
    avatar = models.ImageField(upload_to = 'media/avatars', blank = True, null = True)
    country = models.CharField(blank = True, max_length = 10, verbose_name = "Country code")
    custom_css = models.URLField(blank=True)
    email_on_artist_add = models.BooleanField(default=True, verbose_name = "Send email on artist approval")
    email_on_artist_comment = models.BooleanField(default = True, verbose_name="Send email on artist comments")
    email_on_group_add = models.BooleanField(default=True, verbose_name = "Send email on group/label approval")
    email_on_pm = models.BooleanField(default=True, verbose_name = "Send email on new PM")
    fave_id = models.IntegerField(blank = True, null = True, verbose_name = "Fave SongID", help_text="SongID number of *the* song you love the most!")
    group = models.ForeignKey(Group, null = True, blank = True)
    hol_id = models.IntegerField(blank=True, null = True, verbose_name="H.O.L. ID", help_text="If you have a Hall of Light ID number (Amiga Developers) - See http://hol.abime.net")
    icq_id = models.CharField(blank = True, max_length = 40, verbose_name = "ICQ Number", help_text="ICQ Number for people to contact you (optional)")
    infoline = models.CharField(blank = True, max_length = 50)
    info = models.TextField(blank = True, verbose_name="Profile Info", help_text="Enter a little bit about yourself. No HTML. BBCode tags allowed")
    last_active = models.DateTimeField(blank = True, null = True)
    last_changed = models.DateTimeField(default=datetime.datetime.now())
    last_activity = models.DateTimeField(blank = True, null = True, db_index=True)
    location = models.CharField(blank = True, max_length=40, verbose_name="Hometown Location")
    paginate_favorites = models.BooleanField(default = True)
    pm_accepted_upload = models.BooleanField(default=True, verbose_name = "Send PM on accepted upload")
    real_name = models.CharField(blank = True, max_length = 40, verbose_name = "Real Name", help_text="Your real name (optional)")
    theme = models.ForeignKey(Theme, blank = True, null = True)
    token = models.CharField(blank = True, max_length=32)
    twitter_id = models.CharField(blank = True, max_length = 32, verbose_name = "Twitter ID", help_text="Enter your Twitter account name, without the Twitter URL (optional)")
    user = models.ForeignKey(User, unique = True)
    use_tags = models.BooleanField(verbose_name="Show tags", default = True)
    visible_to = models.CharField(max_length=1, default = "A", choices = VISIBLE_TO)
    web_page = models.URLField(blank = True, verbose_name="Website", help_text="Your personal website address. Must be a valid URL")
    yahoo_id = models.CharField(blank = True, max_length = 40, verbose_name = "Yahoo! ID", help_text="Yahoo! IM ID, for people to contact you (optional)")

    def save(self, *args, **kwargs):
        self.last_changed = datetime.datetime.now()
        return super(Userprofile, self).save(*args, **kwargs)

    def have_artist(self):
        try:
            return self.user.artist
        except:
            return False

    def __unicode__(self):
        return self.user.username

    def get_token(self):
        if not self.token:
            import md5
            self.token = md5.new(self.user.username + settings.SECRET_KEY).hexdigest()
            self.save()
        return self.token

    def viewable_by(self, user):
        if (self.visible_to == 'A') or ((self.visible_to == 'R') and (user.is_authenticated())):
            return True
        return False

    def get_littleman(self):
        stat, image = self.get_status()
        if(image == ""):
            return "user.png"
        return image

    def get_css(self):
        if self.custom_css:
            return self.custom_css
        if self.theme:
            return self.theme.css
        return getattr(settings, 'DEFAULT_CSS', "%sthemes/default/style.css" % settings.MEDIA_URL)

    def get_stat(self):
        stat, image = self.get_status()
        return stat

    def get_status(self):
        if self.user.is_superuser:
            return ("Admin","user_gray.png")
        if self.user.is_staff:
            return ("Staff","user_suit.png")
        if not self.user.is_active:
            return ("Inactive user","user_error.png")
        if self.user.is_active:
            return ("User","user.png")
        return ("Normal user","user.png")

    @models.permalink
    def get_absolute_url(self):
        return ('dv-profile', [self.user.name])

# Label/Producer - Depending on the content being served, this could be a number of things. If serving
#   Real music, this would be the music label such as EMI Records, etc. If this is for game/computer music
#   It can be used as a Publisher/Producer, such as Ocean Software, Gremlin Graphics etc.
class Label(models.Model):
    STATUS_CHOICES = (
            ('A', 'Active'),
            ('I', 'Inactive'),
            ('D', 'Dupe'),
            ('U', 'Uploaded'),
            ('R', 'Rejected')
        )

    cease_date = models.DateField(help_text="Date label was closed/went out of business (YYYY-MM-DD)", null=True, blank = True)
    created_by = models.ForeignKey(User,  null = True, blank = True, related_name="label_createdby")
    found_date = models.DateField(help_text="Date label was formed (YYYY-MM-DD)", null=True, blank = True)
    hol_id = models.IntegerField(blank=True, null = True, verbose_name="H.O.L. ID", help_text="Hall of Light ID number (Amiga) - See http://hol.abime.net")
    info = models.TextField(blank = True, help_text="Additional information about this label. No HTML.")
    label_icon = models.ImageField(upload_to = 'media/labels/icons', blank = True, null = True, verbose_name="Label Icon (Shows instead of default icon)", help_text="Upload an image containing the icon for this label")
    last_updated = models.DateTimeField(editable = False, blank = True, null = True)
    logo = models.ImageField(upload_to = 'media/labels', blank = True, null = True, verbose_name="Label Logo", help_text="Upload an image containing the logo for this label")
    name = models.CharField(max_length=40, unique = True, db_index = True, verbose_name="* Name", help_text="Name of this label, as you want it to appear on the site")
    pouetid = models.IntegerField(blank=True, null = True, verbose_name="Pouet ID", help_text="If this label has a pouet group entry, enter the ID here.")
    startswith = models.CharField(max_length=1, editable = False, db_index = True)
    status = models.CharField(max_length = 1, choices = STATUS_CHOICES, default = 'A')
    webpage = models.URLField(blank=True, verbose_name="Website", help_text="Website for this label, if available")
    wiki_link = models.URLField(blank=True, help_text="Full URL to wikipedia entry (if available)")

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        S = self.name[0].lower()
        if not S in alphalist:
            S = '#'
        self.startswith = S
        self.last_updated = datetime.datetime.now()
        return super(Label, self).save(*args, **kwargs)

    @models.permalink
    def get_absolute_url(self):
        return ('dv-label', [str(self.id)])

class Artist(models.Model):
    STATUS_CHOICES = (
            ('A', 'Active'),
            ('I', 'Inactive'),
            ('V', 'Not verified'),
            ('D', 'Dupe'),
            ('U', 'Uploaded'),
            ('R', 'Rejected')
        )

    alias_of = models.ForeignKey('self', null = True, blank = True, related_name='aliases')
    artist_pic = models.ImageField(verbose_name="Picture", help_text="Insert a picture of this artist.", upload_to = 'media/artists', blank = True, null = True)
    created_by = models.ForeignKey(User,  null = True, blank = True, related_name="artist_createdby")
    deceased_date = models.DateField(help_text="Date of Passing (YYYY-MM-DD)", null=True, blank = True, verbose_name="Date Of Death")
    dob = models.DateField(help_text="Date of Birth (YYYY-MM-DD)", null=True, blank = True)
    groups = models.ManyToManyField(Group, null = True, blank = True, help_text="Select any known groups this artist is a member of.")
    handle = models.CharField(max_length=64, unique = True, db_index = True, verbose_name="* Handle", help_text="Artist handle/nickname. If no handle is used, place their real name here (and not in the above real name position) to avoid duplication")
    hol_id = models.IntegerField(blank=True, null = True, verbose_name="H.O.L. ID", help_text="Hall of Light Artist ID number (Amiga) - See http://hol.abime.net")
    home_country = models.CharField(blank = True, max_length = 10, verbose_name = "Country Code", help_text="Standard country code, such as gb, us, ru, se etc.")
    home_location = models.CharField(blank = True, max_length=40, verbose_name="Location", help_text="Hometown location, if known.")
    info = models.TextField(blank = True, help_text="Additional artist information. No HTML allowed.")
    is_deceased = models.BooleanField(default=False, verbose_name = "Deceased?", help_text="Has this artist passed away? Check if this has happened.")
    labels = models.ManyToManyField(Label, null = True, blank = True, help_text="Select any known production labels associated with this artist.") # Production labels this artist has worked for
    last_fm_id = models.CharField(blank = True, max_length = 32, verbose_name = "Last.fm ID", help_text="If this artist has a Last.FM account, specify the username portion here. Use + instead of Space. Example: Martin+Galway")
    last_updated = models.DateTimeField(editable = False, blank = True, null = True)
    link_to_user = models.OneToOneField(User, null = True, blank = True)
    name = models.CharField(max_length=64, blank = True, verbose_name="Name", help_text="Artist name (First and Last)")
    startswith = models.CharField(max_length=1, editable = False, db_index = True)
    status = models.CharField(max_length = 1, choices = STATUS_CHOICES, default = 'A')
    twitter_id = models.CharField(blank = True, max_length = 32, verbose_name = "Twitter ID", help_text="Enter the Twitter account name of the artist, if known (without the Twitter URL)")
    webpage = models.URLField(blank=True, verbose_name="Website", help_text="Website for this artist. Must exist on the web.")
    wiki_link = models.URLField(blank=True, help_text="URL to Wikipedia entry (if available)")

    def __unicode__(self):
        return self.handle

    class Meta:
        ordering = ['handle']

    def save(self, *args, **kwargs):
        S = self.handle[0].lower() #Stores the first character in the DB, for easier lookup
        if not S in alphalist:
                S = '#'
        self.startswith = S
        self.last_updated = datetime.datetime.now()
        return super(Artist, self).save(*args, **kwargs)

    @models.permalink
    def get_absolute_url(self):
        return ( 'dv-artist', [str(self.id)])

class ArtistVote(models.Model):
    """
    Quick idea I had for an artist rating system. Rather than existing vote methods, it will allow
    Users to give a 'Thumbs Up' to any artist. A value of 0 represents no vote, 1 represents a thumbs
    Up, 2 represents 'OK' and 3 represents a thumbs down. any other number is disqualified. It's
    Kind of like the ratings on poeut a bit too hehe. AAK
    """
    artist = models.ForeignKey(Artist)
    VOTE_CHOICES = (
            ('U', 'Thumbs Up'),
            ('N', 'Neutral'),
            ('D', 'Thumbs Down')
        )
    rating = models.CharField(max_length = 1, choices = VOTE_CHOICES, default = 'U')
    comment = models.CharField(max_length=250, verbose_name="Comment", help_text="Enter your comments about this artist. 1 entry per user.")
    user = models.ForeignKey(User)
    added = models.DateTimeField(auto_now_add=True)

class SongType(models.Model):
    title = models.CharField(max_length=64, unique = True)
    description = models.TextField()
    symbol = models.ImageField(upload_to = 'media/songsource/symbol', blank = True, null = True)
    image = models.ImageField(upload_to = 'media/songsource/image', blank = True, null = True)

    def __unicode__(self):
        return self.title

    class meta:
        ordering = ['title']
        verbose_name = 'Song Source'

    @models.permalink
    def get_absolute_url(self):
        return ("dv-source", [str(self.id)])

class SongPlatform(models.Model):
    title = models.CharField(max_length=64, unique = True)
    description = models.TextField()
    symbol = models.ImageField(upload_to = 'media/platform/symbol', blank = True, null = True)
    image = models.ImageField(upload_to = 'media/platform/image', blank = True, null = True)

    def __unicode__(self):
        return self.title

    class Meta:
        ordering = ['title']

    @models.permalink
    def get_absolute_url(self):
        return ("dv-platform", [str(self.id)])

class Logo(models.Model):
    file = models.FileField(upload_to = 'media/logos')
    active = models.BooleanField(default=True, db_index=True)
    creator = models.CharField(max_length=60)
    description = models.TextField(blank = True)
    def __unicode__(self):
        return self.description or self.creator

    def get_absolute_url(self):
        return self.file.url

class Song(models.Model):
    STATUS_CHOICES = (
            ('A', 'Active'),
            ('B', 'Banned'),
            ('J', 'Jingle'),
            ('I', 'Inactive'),
            ('V', 'Not verified'),
            ('D', 'Dupe'),
            ('E', 'Reported'),
            ('U', 'Uploaded'),
            ('M', 'Moved'), # Moved to CVGM/Necta (Depending on content, see [thread]286[/thread] on Necta)
            ('N', 'Needs Re-Encoding'), # Technically, this track can still play even though it needs re-encoded. AAK
            ('C', 'Removed By Request'), # If we are asked to remove a track. AAK
            ('R', 'Rejected')
        )
    added = models.DateTimeField(auto_now_add=True)
    al_id = models.IntegerField(blank=True, null = True, verbose_name="Atari Legends ID", help_text="Atari Legends ID Number (Atari) - See http://www.atarilegend.com")
    artists = models.ManyToManyField(Artist, null = True, blank = True, help_text="Select all artists involved with creating this song. ")
    bitrate = models.IntegerField(blank = True, null = True)
    cvgm_id = models.IntegerField(blank = True, null = True, verbose_name = "CVGM SongID", help_text="SongID on CVGM (Link will be provided)")
    dtv_id = models.IntegerField(blank=True, null = True, help_text="Demoscene TV number (id_prod= number) from Demoscene.tv", verbose_name="Demoscene.TV")
    explicit = models.BooleanField(default=False, verbose_name = "Explicit Lyrics?", help_text="Place a checkmark in the box to flag this song as having explicit lyrics/content")
    file = models.FileField(upload_to='media/music', verbose_name="File", help_text="Select an MP3 file to upload. The MP3 should be between 128 and 320Kbps, with a Constant Bitrate.")
    groups = models.ManyToManyField(Group, null = True, blank = True)
    hol_id = models.IntegerField(blank=True, null = True, verbose_name="H.O.L. ID", help_text="Hall of Light ID number (Amiga) - See http://hol.abime.net")
    hvsc_url = models.URLField(blank=True, verbose_name="HVSC Link", help_text="Link to HVSC SID file as a complete URL (C64) - See HVSC or alt. mirror (such as www.andykellett.com/music )")
    info = models.TextField(blank = True, help_text="Additional Song information. BBCode tags are supported. No HTML.")
    labels = models.ManyToManyField(Label, null = True, blank = True) # Production labels
    last_changed = models.DateTimeField(auto_now = True)
    lemon_id = models.IntegerField(blank=True, null = True, verbose_name="Lemon64 ID", help_text="Lemon64 Game ID (C64 Only) - See http://www.lemon64.com")
    locked_until = models.DateTimeField(blank = True, null = True)
    loopfade_time = models.PositiveIntegerField(default = 0, verbose_name = "Loop fade time", help_text = "In seconds, 0 = disabled")
    necta_id = models.IntegerField(blank = True, null = True, verbose_name = "Necta SongID", help_text="SongID on Nectarine (Link will be provided)")
    num_favorited = models.IntegerField(default = 0)
    platform = models.ForeignKey(SongPlatform, null = True, blank = True)
    pouetid = models.IntegerField(blank=True, null = True, help_text="Pouet number (which= number) from Pouet.net", verbose_name="Pouet ID")
    projecttwosix_id = models.IntegerField(blank=True, null = True, verbose_name="Project2612 ID", help_text="Project2612 ID Number (Genesis / Megadrive) - See http://www.project2612.org")
    rating = models.FloatField(blank = True, null = True)
    rating_total = models.IntegerField(default = 0)
    rating_votes = models.IntegerField(default = 0)
    replay_gain = models.FloatField(default = 0, verbose_name = _("Replay gain"))
    release_year = models.CharField(blank = True, null = True, verbose_name="Release Year", help_text="Year the song was released (Ex: 1985)", max_length="4", db_index=True)
    remix_of_id = models.IntegerField(blank = True, null = True, verbose_name = "Mix SongID", help_text="Song number (such as: 252) of the original song this is mixed from.", db_index=True)
    samplerate = models.IntegerField(blank = True, null = True)
    song_length = models.IntegerField(blank = True, null = True)
    startswith = models.CharField(max_length=1, editable = False, db_index = True)
    status = models.CharField(max_length = 1, choices = STATUS_CHOICES, default = 'A')
    times_played = models.IntegerField(null = True, default = 0)
    title = models.CharField(verbose_name="* Song Name", help_text="The name of this song, as it should appear in the database", max_length=80, db_index = True)
    type = models.ForeignKey(SongType, null = True, blank = True, verbose_name = 'Source')
    uploader = models.ForeignKey(User,  null = True, blank = True)
    wos_id = models.CharField(max_length=8, blank=True, null = True, verbose_name="W.O.S. ID", help_text="World of Spectrum ID Number (Spectrum) such as 0003478 (leading 0's are IMPORTANT!) - See http://www.worldofspectrum.org")
    zxdemo_id = models.IntegerField(blank=True, null = True, verbose_name="ZXDemo ID", help_text="ZXDemo Production ID Number (Spectrum) - See http://www.zxdemo.org")

    objects = models.Manager()
    active = ActiveSongManager()

    class Meta:
        ordering = ['title']

    @models.permalink
    def get_absolute_url(self):
        return ("dv-song", [str(self.id)])

    def length(self):
        """
        Returns song length in minutes:seconds format
        """
        if self.song_length:
            return "%d:%02d" % ( self.song_length/60, self.song_length % 60 )
        return "Not set"

    def set_song_data_lazy(self):
        #use length or replaygain as indicator if song has had a propper scan yet
        #this avoids unnessessary multiple passes
        if (not self.song_length) or self.song_length == 0 \
            or (not self.replay_gain) or self.replay_gain == 0:
            self.set_song_data()
        
    def set_song_data(self):
        if dscan.is_configured():
            self.set_song_data_demosauce()
        else:
            self.set_song_data_pymad()

    def set_song_data_demosauce(self):
        df = dscan.ScanFile(self.file.path)
        if not df.readable:
            return            
        threshold = getattr(settings, 'LOOPINESS_THRESHOLD', False)
        looplength = getattr(settings, 'LOOP_LENGTH', False)
        
        self.song_length = df.length
        self.replay_gain = df.replaygain()
        self.samplerate = df.samplerate
        self.bitrate = df.bitrate  
        if not looplength:
            looplength = 120
        if threshold and threshold > 0 and df.loopiness > threshold:
            self.loopfade_time = max(looplength, self.song_length)
			        
    def set_song_data_pymad(self):
        mf = mad.MadFile(self.file.path)
        seconds = mf.total_time() / 1000
        bitrate = mf.bitrate() / 1000
        samplerate = mf.samplerate()
        self.song_length = seconds
        self.bitrate = bitrate
        self.samplerate = samplerate

    def get_pouet_screenshot(self):
        """
        Simple XML retrival system for recovering data from pouet.net xml files. Eventually,
        I'll add code to recover more elements from pouet. AAK.
        """
        if self.pouetid:
            try:
                pouetlink = "http://www.pouet.net/export/prod.xnfo.php?which=%d" % (self.pouetid)
                usock = urllib.urlopen(pouetlink)
                xmldoc = xml.dom.minidom.parse(usock)
                usock.close()

                # Parse the <screenshot> tag out of the doc, if it exists
                screen = xmldoc.getElementsByTagName('screenshot')[0].childNodes[1]
                imglink = screen.firstChild.nodeValue

                t = loader.get_template('webview/t/pouet_screenshot.html')
                c = Context ( { 'object' : self,
                               'imglink' : imglink } )
                return t.render(c)

            except:
                return "Couldn't pull Pouet info!"

    def get_pouet_download(self):
        """
        Recover first download link from Pouet XML. AAK.
        """
        if self.pouetid:
            try:
                pouetlink = "http://www.pouet.net/export/prod.xnfo.php?which=%d" % (self.pouetid)
                usock = urllib.urlopen(pouetlink)
                xmldoc = xml.dom.minidom.parse(usock)
                usock.close()

                # Parse the <screenshot> tag out of the doc, if it exists
                screen = xmldoc.getElementsByTagName('download')[0].childNodes[1]
                dllink = screen.firstChild.nodeValue

                t = loader.get_template('webview/t/pouet_download.html')
                c = Context ( { 'object' : self,
                               'dllink' : dllink } )
                return t.render(c)

            except:
                pass

    def save(self, *args, **kwargs):
        #I don't think this is still needed
        #~ if not self.id or self.song_length == None:
            #~ try:
                #~ self.set_song_data_lazy()
            #~ except:
                #~ # This causes the record to not contain anything until the
                #~ # 'Not Set' bug is fixed. The result; Admins can Edit/Save
                #~ # Song faster to re-set song time. AAK.
                #~ self.song_length = None
                #~ self.bitrate = None
                #~ self.samplerate = None
            #~ try:
                #~ del mf
            #~ except:
                #~ pass
        S = self.title[0].lower()
        if not S in alphalist:
            S = '#'
        self.startswith = S
        return super(Song, self).save(*args, **kwargs)

    def artist(self):
        """
        Returns the artists connected to the song as a string.

        Format: Artist1, Artist2, Artist3
        """
        artists = self.artists.all()
        groups = self.groups.all()
        A = []
        for x in artists:
            A.append(x.handle)
        for x in groups:
            A.append(x.name)
        return ', '.join(A)

    def __unicode__(self):
        return self.title

    def last_queued(self):
        """
        Returns either the time the song was last queued, or 'Never'

        Note: This works on when it was queued, not played.
        """
        logging.debug("Getting last queued time for song %s" % self.id)
        key = "songlastplayed_%s" % self.id
        c = cache.get(key)
        if not c:
            logging.debug("No cache for last queued, finding")
            Q = Queue.objects.filter(song=self).order_by('-id')[:1]
            if not Q:
                c = "Never"
            else:
                c = Q[0].requested
            cache.set(key, c, 5)
        return c

    def is_locked(self):
        """
        Determines if the song is locked.

        This function compares the time it was last queued
        """
        if self.status != 'A' and self.status != 'N':
            return True
        #last = self.last_queued()
        if not self.locked_until or self.locked_until < datetime.datetime.now():
            return False
        return True

    def is_favorite(self, user):
        q = Favorite.objects.filter(user=user, song=self)
        if q:
            return True
        return False

    def set_vote(self, vote, user):
        if vote < 1:
            return False
        if not SongVote.objects.filter(song=self, user=user):
            #New vote
            self.rating_total += vote
            self.rating_votes += 1
            vt = SongVote(user = user, song = self, vote = vote)
        else:
            #Change existing vote
            vt = SongVote.objects.get(user=user, song = self)
            self.rating_total = (self.rating_total - vt.vote) + vote
            vt.vote = vote
        vt.save()
        self.rating = float(self.rating_total) / self.rating_votes
        self.save()
        return True

    def get_vote(self, user):
        vote = SongVote.objects.filter(song=self, user=user)
        if vote:
            return vote[0].vote
        return ""

    def queue_by(self, user, force = False):
        result = True
        Queue.objects.lock(Song, User, AjaxEvent)
        if not force:
            requests = Queue.objects.filter(played=False, requested_by = user).count()
            if requests >= settings.SONGS_IN_QUEUE:
                add_event(event='eval:alert("You have reached your queue limit. Wait for the songs to play.");', \
                    user = user)
                result = False
            if self.is_locked():
                result = False
        if result:
            Q = Queue(song=self, requested_by=user, played = False)
            Q.save()
            add_event(event='a_queue_%i' % self.id)
        Queue.objects.unlock()
        return result
try:
    tagging.register(Song)
except tagging.AlreadyRegistered:
    pass

class TagHistory(models.Model):
    song = models.ForeignKey(Song)
    tags = models.TextField(blank=True)
    user = models.ForeignKey(User)
    added = models.DateTimeField(auto_now_add=True)

class SongVote(models.Model):
    song = models.ForeignKey(Song)
    vote = models.IntegerField()
    user = models.ForeignKey(User)
    added = models.DateTimeField(auto_now_add=True)

class Compilation(models.Model):
    """
    Simplified Album/Compilation class. Designed to try and merge the demoscene/real music
    Barrier with released productions. Might not be used all the time, though it would be
    Handy for some musicians to take advantage of, such as Machinae Supremacy or other demoscene
    Artists who want to promote some badass tracks from their upcoming CD. Linkage FTW!!!111   AAK
    """
    STATUS_CHOICES = (
            ('A', 'Active'),
            ('I', 'Inactive'),
            ('D', 'Dupe'),
            ('N', 'Need More Info'),
            ('F', 'Fake'),
            ('U', 'Uploaded'),
            ('R', 'Rejected')
        )

    bar_code = models.CharField(help_text="UPC / Bar Code Of Product", max_length=30, blank = True) # Optional bar code number for CD
    comp_icon = models.ImageField(help_text="Album Icon (Shows instead of default icon)", upload_to = 'media/compilations/icons', blank = True, null = True) # Album Artwork
    cover_art = models.ImageField(help_text="Album Cover/Screenshot", upload_to = 'media/compilations', blank = True, null = True) # Album Artwork
    created_by = models.ForeignKey(User, null = True, blank = True)
    date_added = models.DateTimeField(auto_now_add=True) # Date the compilation added to the DB
    details_page = models.URLField(help_text="External link to info page about the compilation", blank = True) # Link to external website about the compilation, such as demoparty page
    download_link = models.URLField(help_text="Link to download the production (in any format)", blank = True) # Download Link
    hol_id = models.IntegerField(blank=True, null = True, verbose_name="H.O.L. ID", help_text="Hall of Light ID number (Amiga) - See http://hol.abime.net")
    info = models.TextField(help_text="Description, as you want it to appear on the site. BBCode tags supported. No HTML.", blank = True) # Info page, which will be a simple textbox entry such as a description field
    label = models.CharField(verbose_name="Prod. Label", help_text="Production label/Distributor of this compilation. Will appear as [name] by [label]", max_length=30, blank = True) # Record label produced under, if applicable (Not always tied to a specific group/artist)
    last_updated = models.DateTimeField(blank = True, null = True)
    media_format = models.CharField(help_text="Usually CD/DVD/FLAC/MP3/OGG etc.", max_length=30, blank = True) # Optional media format, such as CD/DVD/FLAC/MP3 etc.
    name = models.CharField(max_length=80, unique = True, db_index = True, verbose_name="* Name", help_text="Name of the compilation, as you want it to appear on the site") # Name of the compilation
    num_discs = models.IntegerField(help_text="If this is a media format like CD, you can specify the number of disks", blank=True, null = True) # Number of discs in the compilation
    pouet = models.IntegerField(help_text="Pouet ID for compilation", blank=True, null = True) # If the production has a pouet ID
    prod_artists = models.ManyToManyField(Artist, verbose_name="Production Artists", help_text="Artists associated with the production of this compilation (not necessarily the same as the tracks)", null = True, blank = True) # Internal artists involved in the production
    prod_groups = models.ManyToManyField(Group, verbose_name="Production Groups", help_text="Groups associated with the production of this compilation (not necessarily the same as the tracks)", null = True, blank = True) # Internal groups involved in the production
    prod_notes = models.TextField(help_text="Production notes, from the author/group/artists specific to the making of this compilation", blank = True) # Personalized production notes
    projecttwosix_id = models.IntegerField(blank=True, null = True, verbose_name="Project2612 ID", help_text="Project2612 ID Number (Genesis / Megadrive) - See http://www.project2612.org")
    purchase_page = models.URLField(help_text="If this is a commercial product, you can provide a 'Buy Now' link here", blank = True) # If commercial CD, link to purchase the album
    rel_date = models.DateField(help_text="Original Release Date", null=True, blank = True) # Original release date, we could also add re-release date though not necessary just yet!
    running_time = models.IntegerField(help_text="Overall running time (In Seconds)", blank = True, null = True) # Running time of the album/compilation
    songs = models.ManyToManyField(Song, null = True, blank = True)
    startswith = models.CharField(max_length=1, editable = False, db_index = True) # Starting letter for search purposes
    status = models.CharField(max_length = 1, choices = STATUS_CHOICES, default = 'A')
    wiki_link = models.URLField(blank=True, help_text="URL to wikipedia entry (if available)")
    youtube_link = models.URLField(help_text="Link to Youtube/Google Video Link (external)", blank = True) # Link to a video of the production
    zxdemo_id = models.IntegerField(blank=True, null = True, verbose_name="ZXDemo ID", help_text="ZXDemo Production ID Number (Spectrum) - See http://www.zxdemo.org")

    class Meta:
        ordering = ['name']

    def length(self):
        """
        Returns compilation length in minutes:seconds format
        """
        if self.running_time:
            return "%d:%02d" % ( self.running_time/60, self.running_time % 60 )
        return "Not set"

    def save(self, *args, **kwargs):
        S = self.name[0].lower() #Stores the first character in the DB, for easier lookup
        if not S in alphalist:
                S = '#'
        self.startswith = S
        return super(Compilation, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ('dv-compilation', [str(self.id)])

class CompilationVote(models.Model):
    """
    Same voting methods for thumbs up rating, only for specific compilations. AAK
    """
    comp = models.ForeignKey(Compilation)
    vote = models.IntegerField(default=0)
    user = models.ForeignKey(User)
    added = models.DateTimeField(auto_now_add=True)

class SongApprovals(models.Model):
    song = models.ForeignKey(Song)
    approved = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(User, related_name="uploadlist_approvedby")
    uploaded_by = models.ForeignKey(User, related_name="uploadlist_uploadedby")

class SongDownload(models.Model):
    song = models.ForeignKey(Song)
    title = models.CharField(max_length=64)
    download_url = models.CharField(unique = True, max_length=200)
    added = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['title']

class Queue(models.Model):
    eta = models.DateTimeField(blank = True, null = True)
    played = models.BooleanField(db_index = True)
    playtime = models.DateTimeField(blank = True, null = True, db_index = True)
    priority = models.BooleanField(default=False, db_index = True)
    requested_by = models.ForeignKey(User)
    requested = models.DateTimeField(auto_now_add=True, db_index = True)
    song = models.ForeignKey(Song)
    time_played = models.DateTimeField(blank = True, null = True, db_index = True)

    objects = LockingManager()

    def __unicode__(self):
        return self.song.title

    def timeleft(self):
        if self.song.song_length == None or not self.played:
            return 0
        delta = datetime.datetime.now() - self.time_played
        return self.song.song_length - delta.seconds

    def get_eta(self):
        if self.id:
            baseq = Queue.objects.filter(played=False).exclude(id=self.id)
            baseq_lt = Queue.objects.filter(played=False, id__lt=self.id)
        else:
            baseq = baseq_lt = Queue.objects.filter(played=False)
        try :
            playtime = Queue.objects.select_related(depth=2).filter(played=True).order_by('-time_played')[0].timeleft()
        except IndexError:
            playtime = 0
        if self.priority:
            if not self.playtime:
                for q in baseq_lt.filter(priority = True):
                    playtime = playtime + q.song.song_length
                return datetime.datetime.now() + datetime.timedelta(seconds=playtime)

            else:
                for q in baseq_lt.filter(priority = True):
                    #Not quite sure how to do this right now, returning self.playtime for now
                    pass
                return self.playtime
        for q in baseq_lt.filter(playtime = None, priority = False):
            playtime = playtime + q.song.song_length
        for q in baseq.filter(priority = True):
            playtime = playtime + q.song.song_length
        eta = datetime.datetime.now() + datetime.timedelta(seconds=playtime)
        for q in baseq.filter(playtime__lt = eta):
            playtime = playtime + q.song.song_length
        eta = datetime.datetime.now() + datetime.timedelta(seconds=playtime)
        if self.playtime and self.playtime > eta:
            return self.playtime
        return eta

    def set_eta(self):
         self.eta = self.get_eta()

class SongComment(models.Model):
    song = models.ForeignKey(Song)
    user = models.ForeignKey(User)
    comment = models.TextField()
    added = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.comment
    class Meta:
        ordering = ['-added']

class Favorite(models.Model):
    song = models.ForeignKey(Song)
    user = models.ForeignKey(User)
    added = models.DateTimeField(auto_now_add=True)
    comment = models.TextField()

    def __unicode__(self):
        return self.song.title

    class Meta:
        unique_together = ("user", "song")
        ordering = ['song']

    def save(self, *args, **kwargs):
        if not self.id:
            self.song.num_favorited += 1
            self.song.save()
        return super(Favorite, self).save(*args, **kwargs)

    def delete(self):
        self.song.num_favorited -= 1
        self.song.save()
        return super(Favorite, self).delete()

class Oneliner(models.Model):
    message = models.CharField(max_length=256)
    user = models.ForeignKey(User)
    added = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-added']
        permissions = (
            ('mute_oneliner',"Muted from oneliner"),
        )

    def save(self, *args, **kwargs):
        return super(Oneliner, self).save(*args, **kwargs)

class AjaxEvent(models.Model):
    event = models.CharField(max_length=100)
    user = models.ForeignKey(User, blank = True, null = True, default = None)

class News(models.Model):
    text = models.TextField()
    title = models.CharField(max_length=100)
    STATUS = (
        ('A', 'Active'),
        ('S', 'Sticky'),
        ('L', 'Logged in users'),
        ('I', 'Inactive'),
        ('B', 'Sidebar'),
    )
    status = models.CharField(choices=STATUS, max_length=1)
    added = models.DateTimeField(auto_now_add=True, db_index=True)
    last_updated = models.DateTimeField(editable = False, blank = True, null = True)
    icon = models.URLField(blank = True)

    def __unicode__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.last_updated = datetime.datetime.now()
        return super(News, self).save(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'News'
        ordering = ['-added']

class RadioStream(models.Model):
    url = models.CharField(max_length=120, verbose_name="Direct URL", help_text="Direct URL to stream (no m3u). Shoutcast streams include PLS extension")
    name = models.CharField(max_length=120, verbose_name="Stream Name", help_text="Name of the stream, as you want it to appear on the site")
    description = models.TextField(blank=True)
    user = models.ForeignKey(User, null = True, help_text="User hosting the stream")
    country_code = models.CharField(max_length=10, verbose_name="Country Code", help_text="Lower-case country code of the server location")
    bitrate = models.IntegerField()
    STREAMS = (
        ('M', 'MP3'),
        ('O', 'Ogg'),
        ('A', 'AAC'),
        ('S', 'SHOUTcast'),
    )
    streamtype = models.CharField(max_length=1, choices = STREAMS)
    active = models.BooleanField(default=True, db_index=True)

    def __unicode__(self):
        return "%s (%s)" % (self.name, self.bitrate)

class PrivateMessage(models.Model):
    message = models.TextField()
    reply_to = models.ForeignKey('PrivateMessage', blank = True, null = True, default = None)
    sender = models.ForeignKey(User, related_name="sent_messages")
    sent = models.DateTimeField(auto_now_add=True)
    subject = models.CharField(max_length=60)
    to = models.ForeignKey(User)
    unread = models.BooleanField(default=True)
    visible = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-sent']

    def __unicode__(self):
        return self.subject

    @models.permalink
    def get_absolute_url(self):
        return ("dv-read_pm", [str(self.id)])

    def save(self, *args, **kwargs):
        #Check if user have send pm on, and if its a new message
        profile = self.to.get_profile()
        if self.pk == None and profile.email_on_pm:
            mail_from = settings.DEFAULT_FROM_EMAIL
            mail_tpl = loader.get_template('webview/email/new_pm.txt')
            me = Site.objects.get_current()
            mail_subject = "[%s] New Private Message:" % me.name

            c = Context({
                'message' : self,
                'site' : Site.objects.get_current(),
            })

            email = EmailMessage(
                subject=mail_subject+' '+striptags(self.subject),
                body= mail_tpl.render(c),
                from_email=mail_from,
                to=[self.to.email])
            email.send(fail_silently=True)
        #Call real save
        return super(PrivateMessage, self).save(*args, **kwargs)

class UploadTicket(models.Model):
    ticket = models.CharField(max_length=20)
    user = models.ForeignKey(User)
    added = models.DateTimeField(auto_now_add=True)
    tempfile = models.CharField(max_length=100, blank = True, default = "")
    filename = models.CharField(max_length=100, blank = True, default = "")

class CountryList(models.Model):
    name = models.CharField(max_length=60)
    code = models.CharField(max_length=20)
    flag = models.CharField(max_length=20)

    class Meta:
        ordering = ['name']

class LinkCategory(models.Model):
    name = models.CharField(max_length=60, verbose_name="Category Name", help_text="Display Name of this category, as you want to see it on the links page")  # Visible name of the link category
    id_slug = models.SlugField(_("Slug"), help_text="Category slug. Must be unique, and only contain letters, numbers and symbols (No Spaces)")  # Identifier slug; Can be used for searching/indexing link groups later
    description = models.TextField(verbose_name="Description", help_text="A Description of this category. Will appear on the category description.") # Simple description field for the category
    icon = models.ImageField(upload_to = 'media/links/slug_icon', blank = True, null = True, verbose_name="Category Icon", help_text="Specify an icon image to use when displaying this category on the links page") # Specify an icon to use for this link category

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Link Category"
        verbose_name_plural = "Link Categories"

    @models.permalink
    def get_absolute_url(self):
        return ('dv-linkcategory', [self.id_slug])

class Link(models.Model):
    name = models.CharField(unique = True, max_length=40, verbose_name="Link Name", help_text="Name/Title of the link. Depending on link type, might not be displayed.") # Clickable name of the link
    TYPE = (
        ('T', 'Text Link'),
        #('U', 'Button Link'),
        #('B', 'Banner Link'),
    )
    link_type = models.CharField(max_length=1, choices = TYPE, verbose_name="Link Type", help_text="Choose the type of link you want to add", default = 'T') # Determines the type of link being added to the site
    link_url = models.URLField(unique = True, verbose_name="Link URL", help_text="Enter the address you wish to link to. This is where the user will be directed to.")
    link_title = models.CharField(blank = True, null = True, max_length=60, verbose_name="Link Desc.", help_text="Link Description, as you want it to appear on the site")
    link_image = models.ImageField(upload_to = 'media/links/link_image', blank = True, null = True, verbose_name="Link Image", help_text="Image used for this link. Don't use an image bigger than your link type!")
    url_cat = models.ForeignKey(LinkCategory, verbose_name="Link Category", help_text="Which category does this link belong in?") # Category to place the link into
    notes = models.TextField(blank = True, null = True, verbose_name="Link Notes", help_text="Notes/comments about this link to moderator")
    keywords = models.CharField(max_length=60, blank = True, null = True, verbose_name="Keywords", help_text="Keywords associated with this link (comma seperated, optional)")

    submitted_by = models.ForeignKey(User, blank = True, null = True, related_name="label_submittedby")
    approved_by = models.ForeignKey(User, blank = True, null = True, related_name="label_approvedby")
    added = models.DateTimeField(auto_now_add=True, db_index=True) # DateTime from when the link was added to the DB
    last_updated = models.DateTimeField(editable = False, blank = True, null = True)

    STATUS = (
        ('A', 'Active'),
        ('P', 'Pending Approval'),
        ('R', 'Rejected'),
    )
    status = models.CharField(max_length=1, choices = STATUS, default = 'A', db_index=True) # Status of the link in the system
    priority = models.BooleanField(default=False, db_index=True, help_text="If active, link will receive high priority and display in Bold") # Determines higher position in listings

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.last_updated = datetime.datetime.now()
        return super(Link, self).save(*args, **kwargs)

    @models.permalink
    def get_absolute_url(self):
        return ('dv-linkcategory', [self.id])

class Faq(models.Model):
    active = models.BooleanField(default=True, verbose_name = "Active?", db_index=True)
    added_by = models.ForeignKey(User, blank = True, null = True)
    added = models.DateTimeField(auto_now_add=True, db_index=True)
    answer = models.TextField(verbose_name="Answer", help_text="Full answer to FAQ question. Use BBCode as needed.")
    last_updated = models.DateTimeField(editable = False, blank = True, null = True)
    priority = models.IntegerField(help_text="Priority order. Used for sorting questions.", default = 0, blank=True, null = True)
    question = models.CharField(max_length=500, verbose_name="Question", help_text="The question, as it should appear on the FAQ list")

    def __unicode__(self):
        return self.question

    def save(self, *args, **kwargs):
        self.last_updated = datetime.datetime.now()
        return super(Faq, self).save(*args, **kwargs)

    class Meta:
        ordering = ['priority']
        verbose_name = "FAQ"
        verbose_name_plural = "FAQ's"

    @models.permalink
    def get_absolute_url(self):
        return ('dv-faqitem', [self.id])

class Screenshot(models.Model):
    active = models.BooleanField(default=True, verbose_name = "Active?", db_index=True)
    added_by = models.ForeignKey(User, blank = True, null = True, related_name="screenshoit_addedby")
    description = models.TextField(verbose_name="Description", help_text="Brief description about this image, and any other applicable notes.")
    image = models.ImageField(upload_to = 'media/screenshot/image', blank = True, null = True) # Image to be displayed for this screenshot
    last_updated = models.DateTimeField(editable = False, blank = True, null = True)
    name = models.CharField(unique = True, max_length=70, verbose_name="Screen Name", help_text="Name/Title of this screenshot. Be verbose, to make it easier to find later. Use something such as a demo/production/game name.")
    startswith = models.CharField(max_length=1, editable = False, db_index = True)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Eventually, we will add a screenshot browser
        S = self.name[0].lower()
        if not S in alphalist:
            S = '#'
        self.startswith = S
        self.last_updated = datetime.datetime.now()
        return super(Screenshot, self).save(*args, **kwargs)

def create_profile(sender, **kwargs):
    if kwargs["created"]:
        try:
            profile = Userprofile(user = kwargs["instance"])
            profile.save()
        except:
            pass
post_save.connect(create_profile, sender=User)

def set_song_values(sender, **kwargs):
    if kwargs["created"]:
        try:
            song = kwargs["instance"]
            song.set_song_data_lazy()
            song.save()
        except:
            pass
post_save.connect(set_song_values, sender = Song)

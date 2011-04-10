from django.db import models
from django.contrib.auth.models import User
import datetime

import re
import os.path
from django.conf import settings
from django.core.mail import EmailMessage
#from django.core.urlresolvers import reverse
import dscan
import logging
import xml.dom.minidom, urllib # Needed for XML processing
from django.core.cache import cache
from django.template.defaultfilters import striptags
from django.contrib.sites.models import Site
from django.template import Context, loader
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy as _

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

import tagging
import time, hashlib
log = logging.getLogger("webview.models")

CHEROKEE_SECRET = getattr(settings, "CHEROKEE_SECRET_DOWNLOAD_KEY", "")
CHEROKEE_PATH = getattr(settings, "CHEROKEE_SECRET_DOWNLOAD_PATH", "")
CHEROKEE_REGEX = getattr(settings, "CHEROKEE_SECRET_DOWNLOAD_REGEX", "")
CHEROKEE_LIMIT = getattr(settings, "CHEROKEE_SECRET_DOWNLOAD_LIMIT", "")
CHEROKEE_LIMIT_URL = getattr(settings, "CHEROKEE_SECRET_DOWNLOAD_LIMIT_URL", "")

SELFVOTE_DISABLED = getattr(settings, "SONG_SELFVOTE_DISABLED", False)

def download_limit_reached(user):
    limits = get_cherokee_limit(user)
    if limits:
        key = "urlgenlimit_%s" % user.id
        k = cache.get(key, 0)
        if k > limits.get("number"):
            return True

def get_cherokee_limit(user):
    r = {}
    if CHEROKEE_LIMIT and user and user.is_authenticated():
        if CHEROKEE_LIMIT.get("default"):
            L = CHEROKEE_LIMIT.get("default")
        else:
            L = CHEROKEE_LIMIT
        if user.is_superuser and CHEROKEE_LIMIT.get("admin"):
            L = CHEROKEE_LIMIT.get("admin")
        elif user.is_staff and CHEROKEE_LIMIT.get("staff"):
            L = CHEROKEE_LIMIT.get("staff")
        for group in user.groups.all():
            gn = CHEROKEE_LIMIT.get(group.name)
            if gn:
                if gn.get("seconds") >= L.get("seconds") and gn.get("number") >= L.get("number"):
                    L = gn
        r['seconds'] = L.get("seconds", 60*60*24)
        r['number'] = L.get("number", 0)
    return r

def secure_download (url, user=None):
    if CHEROKEE_SECRET:
        limits = get_cherokee_limit(user)
        if limits:
            key = "urlgenlimit_%s" % user.id
            try:
                k = cache.incr(key)
            except:
                k = 1
                cache.set(key, k, limits.get("seconds"))
            if k > limits.get("number"):
                return CHEROKEE_LIMIT_URL or " Limit reached"
        t = '%08x' % (time.time())
        if CHEROKEE_REGEX:
            try:
                url = str(url)
            except:
                url = url.encode("utf8")
            url = re.sub(*CHEROKEE_REGEX + (url,))
        return CHEROKEE_PATH + "/%s/%s/%s" % (hashlib.md5(CHEROKEE_SECRET + "/" + url + t).hexdigest(), t, url)
    return url

if getattr(settings, "LOOKUP_COUNTRY", True):
    from demovibes.ip2cc import ip2cc
    ipdb = os.path.join(settings.SITE_ROOT, "ipcountry.db")
    if not os.path.exists(ipdb):
        log.info("IP2Country DB not found, creating new")
        from ip2cc import update as ip2ccupdate
        ip2ccupdate.create_file(ipdb)
    ipccdb = ip2cc.CountryByIP(ipdb)
else:
    ipccdb = False

uwsgi_event_server = getattr(settings, 'UWSGI_EVENT_SERVER', False)

if uwsgi_event_server:
    uwsgi_event_server_http = getattr(settings, 'UWSGI_EVENT_SERVER_HTTP', False)
    try:
        import uwsgi
    except:
        import pickle
        uwsgi_event_server = "HTTP"

def add_event(event = None, user = None, eventlist = []):
    """
    Add event(s) to the event handler(s)

    Keywords:
    event -- string that will be sent to clients
    user -- optional -- User to receive the event
    eventlist -- List of events to process

    Either event or eventlist must be supplied
    """
    if not event and not eventlist:
        return False

    if event:
        eventlist=[event]

    for event in eventlist:
        ae = AjaxEvent.objects.create(event = event, user = user)

    if uwsgi_event_server:
        R = AjaxEvent.objects.filter(user__isnull=True).order_by('-id')[:20] #Should have time based limit here..
        R = [(x.id, x.event) for x in R]
        data = (R, ae.id+1)
        if uwsgi_event_server:
            if uwsgi_event_server == "HTTP":
                data = {'data': pickle.dumps(data)}
                data = urllib.urlencode(data)
                logging.debug("Event data via http: %s" % data)
                url = uwsgi_event_server_http or "http://127.0.0.1/demovibes/ajax/monitor/new/"
                try:
                    r = urllib.urlopen(url, data)
                except:
                    return False
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
    status = models.CharField(max_length = 1, choices = STATUS_CHOICES, default = 'A', db_index = True)
    webpage = models.URLField(blank=True, verbose_name="Website", help_text="Add the website address for this group, if one exists.")
    wiki_link = models.URLField(blank=True, help_text="URL to wikipedia entry (if available)")

    links = generic.GenericRelation("GenericLink")

    def log(self, user, message):
        return ObjectLog.objects.create(obj=self, user=user, text=message)

    def get_logs(self):
        obj_type = ContentType.objects.get_for_model(self)
        return ObjectLog.objects.filter(content_type__pk=obj_type.id, object_id=self.id)

    def get_active_links(self):
        """
        Return all active generic links
        """
        return self.links.filter(status=0)

    def __unicode__(self):
        return self.name

    def get_songs(self):
        meta = Song.objects.filter(songmetadata__active=True, songmetadata__groups = self)
        return meta

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

class GenericBaseLink(models.Model):
    name = models.CharField(max_length = 20)
    link = models.CharField(max_length = 200, help_text="%linkval% for Link Value")
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to = 'media/linkicons', blank = True, null = True)
    inputinfo = models.TextField(blank=True)
    regex = models.TextField(help_text="Regex to check input value")
    LINKTYPE = (
        ("A", "Artists"),
        ("U", "Users"),
        ("S", "Songs"),
        ("G", "Groups"),
        ("L", "Labels")
    )
    linktype = models.CharField(max_length=1, choices=LINKTYPE)

    def __unicode__(self):
        return u"%s link for %s" % (self.name, self.get_linktype_display())

LINKSTATUS = (
    (0,"Active"),
    (1,"Uploaded"),
    (2,"Disabled"),
)

class GenericLink(models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    link = models.ForeignKey(GenericBaseLink)
    value = models.CharField(max_length = 80)
    status = models.PositiveIntegerField(choices=LINKSTATUS, default=0, db_index = True)
    comment = models.TextField(blank=True)
    user = models.ForeignKey(User, blank=True, null=True)

    def __unicode__(self):
        return u"%s for %s" % (self.link, self.content_object)

    def get_link(self):
        """
        Return complete link
        """
        return self.link.link.replace("%linkval%", self.value)

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
    show_youtube = models.BooleanField(default=True, verbose_name="Show YouTube videoes in Currently Playing")
    theme = models.ForeignKey(Theme, blank = True, null = True)
    token = models.CharField(blank = True, max_length=32)
    twitter_id = models.CharField(blank = True, max_length = 32, verbose_name = "Twitter ID", help_text="Enter your Twitter account name, without the Twitter URL (optional)")
    user = models.ForeignKey(User, unique = True)
    use_tags = models.BooleanField(verbose_name="Show tags", default = True)
    visible_to = models.CharField(max_length=1, default = "A", choices = VISIBLE_TO)
    web_page = models.URLField(blank = True, verbose_name="Website", help_text="Your personal website address. Must be a valid URL")
    yahoo_id = models.CharField(blank = True, max_length = 40, verbose_name = "Yahoo! ID", help_text="Yahoo! IM ID, for people to contact you (optional)")

    links = generic.GenericRelation(GenericLink)

    def set_flag_from_ip(self, ip):
        if ipccdb and not self.country:
            try:
                log.debug("Setting country for %s", self.user.username)
                self.country = ipccdb[ip].lower()
                log.debug("Country set to %s", self.country)
            except:
                self.country = getattr(settings, "DEFAULT_FLAG", "nectaflag")
                log.warn("Profile : Could not find country for %s", ip)

    def get_active_links(self):
        """
        Return all active generic links
        """
        return self.links.filter(status=0)

    def save(self, *args, **kwargs):
        self.last_changed = datetime.datetime.now()
        return super(Userprofile, self).save(*args, **kwargs)

    def have_artist(self):
        """
        Check if user have artist connected to it

        Return artist or False
        """
        try:
            return self.user.artist
        except:
            return False

    def __unicode__(self):
        return self.user.username

    def get_token(self):
        """
        Return unique token for user.

        Can be used for various identification purposes,
        and generate unique urls for users (like queue)
        """
        if not self.token:
            import md5
            self.token = md5.new(self.user.username + settings.SECRET_KEY).hexdigest()
            self.save()
        return self.token

    def viewable_by(self, user):
        """
        Check if a user is allowed to view this user's profile
        """
        if (self.visible_to == 'A') or ((self.visible_to == 'R') and (user.is_authenticated())):
            return True
        return False

    def get_littleman(self):
        """
        Return icon according to user status
        """
        stat, image = self.get_status()
        if(image == ""):
            return "user.png"
        return image

    def get_css(self):
        """
        Return custom user CSS url or site default CSS url
        """
        if self.custom_css:
            return self.custom_css
        if self.theme:
            return self.theme.css
        return getattr(settings, 'DEFAULT_CSS', "%sthemes/default/style.css" % settings.MEDIA_URL)

    def get_stat(self):
        """
        Return user status
        """
        stat, image = self.get_status()
        return stat

    def send_message(self, subject, message, sender, reply_to=False):
        PrivateMessage.objects.create(sender = sender,
            to = self.user,
            message = message,
            subject = subject
        )

    def get_status(self):
        """
        Find and return user status and icon
        """
        if self.user.is_superuser:
            return ("Admin","user_gray.png")
        if self.user.is_staff:
            return ("Staff","user_suit.png")
        if not self.user.is_active:
            return ("Inactive user","user_error.png")
        if self.user.is_active:
            return ("User","user.png")
        return ("Normal user","user.png")

    def get_votecount(self):
        """
        Counts the number of songs this user has voted on
        """
        countlist = SongVote.objects.filter(user=self.user)
        return len(countlist);

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
    status = models.CharField(max_length = 1, choices = STATUS_CHOICES, default = 'A', db_index = True)
    webpage = models.URLField(blank=True, verbose_name="Website", help_text="Website for this label, if available")
    wiki_link = models.URLField(blank=True, help_text="Full URL to wikipedia entry (if available)")

    links = generic.GenericRelation(GenericLink)

    def log(self, user, message):
        return ObjectLog.objects.create(obj=self, user=user, text=message)

    def get_logs(self):
        obj_type = ContentType.objects.get_for_model(self)
        return ObjectLog.objects.filter(content_type__pk=obj_type.id, object_id=self.id)

    def get_active_links(self):
        """
        Return all active generic links
        """
        return self.links.filter(status=0)

    def __unicode__(self):
        return self.name

    def get_songs(self):
        meta = Song.objects.filter(songmetadata__active=True, songmetadata__labels = self)
        return meta

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
    status = models.CharField(max_length = 1, choices = STATUS_CHOICES, default = 'A', db_index = True)
    twitter_id = models.CharField(blank = True, max_length = 32, verbose_name = "Twitter ID", help_text="Enter the Twitter account name of the artist, if known (without the Twitter URL)")
    webpage = models.URLField(blank=True, verbose_name="Website", help_text="Website for this artist. Must exist on the web.")
    wiki_link = models.URLField(blank=True, help_text="URL to Wikipedia entry (if available)")

    links = generic.GenericRelation(GenericLink)

    def log(self, user, message):
        return ObjectLog.objects.create(obj=self, user=user, text=message)

    def get_logs(self):
        obj_type = ContentType.objects.get_for_model(self)
        return ObjectLog.objects.filter(content_type__pk=obj_type.id, object_id=self.id)

    def get_active_links(self):
        """
        Return all active generic links
        """
        return self.links.filter(status=0)

    def __unicode__(self):
        return self.handle

    def get_songs(self):
        meta = Song.objects.filter(songmetadata__active=True, songmetadata__artists = self)
        return meta

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

    def get_songs(self):
        meta = Song.objects.filter(songmetadata__active=True, songmetadata__type = self)
        return meta

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

    def get_songs(self):
        meta = Song.objects.filter(songmetadata__active=True, songmetadata__platform = self)
        return meta

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

class SongMetaData(models.Model):
    user = models.ForeignKey(User, blank = True, null = True)
    added = models.DateTimeField(auto_now_add=True)
    song = models.ForeignKey("Song", db_index=True)
    active = models.BooleanField(default=False, db_index=True)
    checked = models.BooleanField(default=False, db_index = True)

    artists = models.ManyToManyField(Artist, null = True, blank = True, help_text="Select all artists involved with creating this song. ")
    groups = models.ManyToManyField(Group, null = True, blank = True)
    info = models.TextField(blank = True, help_text="Additional Song information. BBCode tags are supported. No HTML.")
    labels = models.ManyToManyField(Label, null = True, blank = True) # Production labels
    platform = models.ForeignKey(SongPlatform, null = True, blank = True)
    release_year = models.CharField(blank = True, null = True, verbose_name="Release Year", help_text="Year the song was released (Ex: 1985)", max_length="4", db_index=True)
    type = models.ForeignKey(SongType, null = True, blank = True, verbose_name = 'Source')
    remix_of_id = models.IntegerField(blank = True, null = True, verbose_name = "Mix SongID", help_text="Song number (such as: 252) of the original song this is mixed from.", db_index=True)
    ytvidid = models.CharField(max_length=30, blank = True, verbose_name="YouTube video ID", help_text="For showing YouTube vid in currently playing")
    ytvidoffset = models.PositiveIntegerField(default=0, verbose_name="YouTube start offset")
    pouetid = models.IntegerField(blank=True, null = True, help_text="Pouet number (which= number) from Pouet.net", verbose_name="Pouet ID")

    comment = models.TextField(blank=True, help_text="Extra information. Only visible to moderators")

    class Meta:
        ordering = ["-active", "-id"]

    def get_remix(self):
        if self.remix_of_id:
            m = Song.objects.filter(id=self.remix_of_id)
            if m:
                return m[0]
        return None

    def get_changelist(self):
        if self.active:
            return []
        fields = ["artists", "groups", "labels", "info", "platform", "release_year", "type", "remix_of_id", "ytvidid", "ytvidoffset", "pouetid"]
        mfields = ["artists", "groups", "labels"]
        meta = self.song.get_metadata()
        result = []
        for f in fields:
            me = getattr(self, f)
            old = getattr(meta, f)
            if f in mfields:
                if list(set(me.all()) ^ set(old.all())):
                    result.append(f)
            else:
                if me != old:
                    result.append(f)
        return result

    def __unicode__(self):
        return self.song.title

    def set_active(self):
        SongMetaData.objects.filter(song=self.song).update(active=False)
        self.active = True
        self.checked = True
        self.save()
        self.song.reset_pouetinfo()
        self.song.save() #For cache updates

class ObjectLog(models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    obj = generic.GenericForeignKey('content_type', 'object_id')

    user = models.ForeignKey(User)
    added = models.DateTimeField(default=datetime.datetime.now())
    text = models.TextField()

    def __unicode__(self):
        return unicode(self.obj)

    def display(self):
        return unicode(self.obj)

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
            ('P', 'Promotion'), # Requested by rams
            ('R', 'Rejected'),
            ('K', 'Kaput') # file doesn't exist or scanner didn't like the song
        )
    added = models.DateTimeField(auto_now_add=True)
    al_id = models.IntegerField(blank=True, null = True, verbose_name="Atari Legends ID", help_text="Atari Legends ID Number (Atari) - See http://www.atarilegend.com")
    artists = models.ManyToManyField(Artist, null = True, blank = True, help_text="Select all artists involved with creating this song. ") #a
    bitrate = models.IntegerField(blank = True, null = True)
    cvgm_id = models.IntegerField(blank = True, null = True, verbose_name = "CVGM SongID", help_text="SongID on CVGM (Link will be provided)")
    dtv_id = models.IntegerField(blank=True, null = True, help_text="Demoscene TV number (id_prod= number) from Demoscene.tv", verbose_name="Demoscene.TV")
    explicit = models.BooleanField(default=False, verbose_name = "Explicit Lyrics?", help_text="Place a checkmark in the box to flag this song as having explicit lyrics/content")
    file = models.FileField(upload_to='media/music', verbose_name="File", max_length=200, help_text="Select a module (mod, xm, etc...) or audio file (mp3, ogg, etc...) to upload. See FAQ for details.")
    groups = models.ManyToManyField(Group, null = True, blank = True) #a
    hol_id = models.IntegerField(blank=True, null = True, verbose_name="H.O.L. ID", help_text="Hall of Light ID number (Amiga) - See http://hol.abime.net")
    hvsc_url = models.URLField(blank=True, verbose_name="HVSC Link", help_text="Link to HVSC SID file as a complete URL (C64) - See HVSC or alt. mirror (such as www.andykellett.com/music )")
    info = models.TextField(blank = True, help_text="Additional Song information. BBCode tags are supported. No HTML.") #a
    labels = models.ManyToManyField(Label, null = True, blank = True) #a Production labels
    last_changed = models.DateTimeField(auto_now = True)
    lemon_id = models.IntegerField(blank=True, null = True, verbose_name="Lemon64 ID", help_text="Lemon64 Game ID (C64 Only) - See http://www.lemon64.com")
    locked_until = models.DateTimeField(blank = True, null = True)
    loopfade_time = models.PositiveIntegerField(default = 0, verbose_name = "Loop fade time", help_text = "In seconds, 0 = disabled")
    necta_id = models.IntegerField(blank = True, null = True, verbose_name = "Necta SongID", help_text="SongID on Nectarine (Link will be provided)")
    num_favorited = models.IntegerField(default = 0)
    platform = models.ForeignKey(SongPlatform, null = True, blank = True) #a
    pouetid = models.IntegerField(blank=True, null = True, help_text="Pouet number (which= number) from Pouet.net", verbose_name="Pouet ID") #a
    projecttwosix_id = models.IntegerField(blank=True, null = True, verbose_name="Project2612 ID", help_text="Project2612 ID Number (Genesis / Megadrive) - See http://www.project2612.org")
    rating = models.FloatField(blank = True, null = True)
    rating_total = models.IntegerField(default = 0)
    rating_votes = models.IntegerField(default = 0)
    replay_gain = models.FloatField(default = 0, verbose_name = _("Replay gain"))
    release_year = models.CharField(blank = True, null = True, verbose_name="Release Year", help_text="Year the song was released (Ex: 1985)", max_length="4", db_index=True) #a
    remix_of_id = models.IntegerField(blank = True, null = True, verbose_name = "Mix SongID", help_text="Song number (such as: 252) of the original song this is mixed from.", db_index=True) #a
    samplerate = models.IntegerField(blank = True, null = True)
    song_length = models.IntegerField(blank = True, null = True)
    startswith = models.CharField(max_length=1, editable = False, db_index = True)
    status = models.CharField(max_length = 1, choices = STATUS_CHOICES, default = 'A', db_index=True)
    times_played = models.IntegerField(null = True, default = 0)
    title = models.CharField(verbose_name="* Song Name", help_text="The name of this song, as it should appear in the database", max_length=80, db_index = True)
    type = models.ForeignKey(SongType, null = True, blank = True, verbose_name = 'Source') #a
    uploader = models.ForeignKey(User,  null = True, blank = True)
    wos_id = models.CharField(max_length=8, blank=True, null = True, verbose_name="W.O.S. ID", help_text="World of Spectrum ID Number (Spectrum) such as 0003478 (leading 0's are IMPORTANT!) - See http://www.worldofspectrum.org")
    pouetlink = models.CharField(max_length=200, blank = True)
    pouetss = models.CharField(max_length=100, blank = True)
    pouetgroup = models.CharField(max_length=100, blank = True)
    pouettitle = models.CharField(max_length=100, blank = True)
    ytvidid = models.CharField(max_length=30, blank = True, verbose_name="YouTube video ID", help_text="For showing YouTube vid in currently playing") #a
    ytvidoffset = models.PositiveIntegerField(default=0, verbose_name="YouTube start offset") #a
    zxdemo_id = models.IntegerField(blank=True, null = True, verbose_name="ZXDemo ID", help_text="ZXDemo Production ID Number (Spectrum) - See http://www.zxdemo.org")
    license = models.ForeignKey("SongLicense", blank=True, null=True)

    objects = models.Manager()
    active = ActiveSongManager()

    links = generic.GenericRelation(GenericLink)

    def is_connected_to(self, user):
        if user and user.is_authenticated():
            up = user.get_profile()
            uartist = up.have_artist()
            if uartist and uartist in self.get_metadata().artists.all():
                return True
        return False

    def downloadable_by(self, user):
        if user.is_authenticated() and not download_limit_reached(user):
            if user.is_staff:
                return True
            if self.license and self.license.downloadable:
                return True
        return False

    def get_file_url(self, user=None):
        return secure_download(self.file.url, user)

    def has_video(self):
        return self.get_metadata().ytvidid

    def get_download_links(self):
        """
        Return all active download links
        """
        return self.songdownload_set.filter(status=0)

    def get_active_links(self):
        """
        Return all active generic links
        """
        return self.links.filter(status=0)

    def is_active(self):
        """
        Check if song is considered active.
        """
        return self.status == "A" or self.status == "N"

    class Meta:
        ordering = ['title']

    def get_metadata(self):
        return self.songmetadata_set.all()[0]

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

    def log(self, user, message):
        return ObjectLog.objects.create(obj=self, user=user, text=message)

    def get_logs(self):
        obj_type = ContentType.objects.get_for_model(self)
        return ObjectLog.objects.filter(content_type__pk=obj_type.id, object_id=self.id)

    def set_song_data_lazy(self):
        #use length or replaygain as indicator if song has had a propper scan yet
        #this avoids unnessessary multiple passes
        if (not self.song_length) or self.song_length == 0 \
            or (not self.replay_gain) or self.replay_gain == 0:
            self.set_song_data()

    def set_song_data(self):
        if dscan.is_configured():
            return self.set_song_data_demosauce()
        else:
            return self.set_song_data_pymad()

    def set_song_data_demosauce(self):
        df = dscan.ScanFile(self.file.path)
        if not df.readable:
            return False
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
        return True

    def set_song_data_pymad(self):
        try:
            import mad
            mf = mad.MadFile(self.file.path)
            seconds = mf.total_time() / 1000
            bitrate = mf.bitrate() / 1000
            samplerate = mf.samplerate()
            self.song_length = seconds
            self.bitrate = bitrate
            self.samplerate = samplerate
            result = True
        except:
            logging.warning("Missing pyMAD, and scan not configured")
            result = False
        return result

    def get_pouetid(self):
        return self.get_metadata().pouetid

    def grab_pouet_info(self, tag, subtag = True):
        """
        Query Pouet XML for information defined by tag.

        Takes two arguments
          tag -- string - Name of tag to find
          subtag -- boolean - Return value of the subtag under tag instead of value of tag - default True
        """
        pouetid = self.get_pouetid()
        if not pouetid:
            return False
        try:
            key = "pouetxml%s" % self.id
            xmldata = cache.get(key)
            if not xmldata:
                pouetlink = "http://www.pouet.net/export/prod.xnfo.php?which=%d" % (pouetid)
                usock = urllib.urlopen(pouetlink)
                xmldata = usock.read()
                usock.close()
                cache.set(key, xmldata, 30)

            xmldoc = xml.dom.minidom.parseString(xmldata)

            node = xmldoc.getElementsByTagName(tag)[0]
            if subtag:
                node = node.childNodes[1]
            data = node.firstChild.nodeValue
            return data
        except:
            return False

    def get_pouet_screenshot(self):
        """
        Simple XML retrival system for recovering data from pouet.net xml files. Eventually,
        I'll add code to recover more elements from pouet. AAK.
        """
        pouetid = self.get_pouetid()
        if pouetid:
            try:
                if not self.pouetss:
                    imglink = self.grab_pouet_info("screenshot")
                    self.pouetss = imglink
                    self.save()

                t = loader.get_template('webview/t/pouet_screenshot.html')
                c = Context ( { 'object' : self.get_metadata(),
                               'imglink' : self.pouetss } )
                return t.render(c)

            except:
                return "Couldn't pull Pouet info!"

    def reset_pouetinfo(self):
        self.pouetss = ""
        self.pouetlink = ""


    def get_pouet_download(self):
        """
        Recover first download link from Pouet XML. AAK.
        """
        pouetid = self.get_pouetid()
        if pouetid:
            try:
                if not self.pouetlink:
                    link = self.grab_pouet_info("download")
                    self.pouetlink = link
                    self.save()

                t = loader.get_template('webview/t/pouet_download.html')
                c = Context ( { 'object' : self,
                               'dllink' : self.pouetlink } )
                return t.render(c)

            except:
                pass

    def save(self, *args, **kwargs):
        if not os.path.isfile(self.file.path):
            self.song_length = None
            self.bitrate = None
            self.samplerate = None
            self.replay_gain = 0
            self.loopfade_time = 0

        self.calc_votes()
        S = self.title[0].lower()
        if not S in alphalist:
            S = '#'
        self.startswith = S
        return super(Song, self).save(*args, **kwargs)


    def artist(self):
        """
        Return the artists connected to the song as a string

        Return format: Artist1, Artist2, Artist3
        """
        data = self.get_metadata()
        artists = data.artists.all()
        groups = data.groups.all()
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
        Return either the time the song was last queued, or 'Never'

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
        Determine if the song is locked.

        This function compares the time it was last queued to self.locked_until
        """
        if not self.is_active():
            return True
        #last = self.last_queued()
        if not self.locked_until or self.locked_until < datetime.datetime.now():
            return False
        return True

    def is_favorite(self, user):
        """
        Check if song is favorite of given user
        """
        q = Favorite.objects.filter(user=user, song=self)
        if q:
            return True
        return False

    def calc_votes(self):
        """
        Calculate vote values of song

        Stores data to the object, but does NOT save. That's your job
        """
        votes = SongVote.objects.filter(song=self)
        if votes:
            data = votes.aggregate(models.Avg('vote'), models.Sum('vote'), models.Count('vote'))
            self.rating_total = data['vote__sum']
            self.rating_votes = data['vote__count']
            self.rating = data['vote__avg']
        else:
            #Added for cases where user giving the only vote is deleted
            self.rating = None
            self.rating_total = 0
            self.rating_votes = 0


    def set_vote(self, vote, user):
        """
        Set new songvote for user, or update existing
        """
        if SELFVOTE_DISABLED and self.is_connected_to(user):
            return False

        if vote < 1:
            return False

        obj, created = SongVote.objects.get_or_create(song = self, user=user, defaults = {'vote': vote})
        if not created:
            obj.vote = vote
            obj.save()

        self.save()
        return True

    def get_vote(self, user):
        """
        Return user's vote for song, or blank string
        """
        vote = SongVote.objects.filter(song=self, user=user)
        if vote:
            return vote[0].vote
        return ""

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
    songs = models.ManyToManyField(Song, null = True, blank = True, through="CompilationSongList")
    startswith = models.CharField(max_length=1, editable = False, db_index = True) # Starting letter for search purposes
    status = models.CharField(max_length = 1, choices = STATUS_CHOICES, default = 'A')
    wiki_link = models.URLField(blank=True, help_text="URL to wikipedia entry (if available)")
    youtube_link = models.URLField(help_text="Link to Youtube/Google Video Link (external)", blank = True) # Link to a video of the production
    zxdemo_id = models.IntegerField(blank=True, null = True, verbose_name="ZXDemo ID", help_text="ZXDemo Production ID Number (Spectrum) - See http://www.zxdemo.org")

    def log(self, user, message):
        return ObjectLog.objects.create(obj=self, user=user, text=message)

    def get_logs(self):
        obj_type = ContentType.objects.get_for_model(self)
        return ObjectLog.objects.filter(content_type__pk=obj_type.id, object_id=self.id)

    def reset_songs(self):
        CompilationSongList.objects.filter(compilation = self).delete()

    def get_songs(self):
        return self.songs.all().order_by("compilationsonglist__index")

    def add_song(self, song, index=0):
        return CompilationSongList.objects.create(compilation=self, song=song, index=index)

    class Meta:
        ordering = ['name']
        permissions = (
            ("make_session", "Can create sessions"),
        )

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

class CompilationSongList(models.Model):
    song = models.ForeignKey("Song")
    compilation = models.ForeignKey("Compilation")
    index = models.PositiveIntegerField(default=0, verbose_name="Song index")

    class Meta:
        ordering = ['index']

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
    status = models.PositiveIntegerField(choices=LINKSTATUS, default=0)

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
    description = models.TextField(blank=True)
    time_played = models.DateTimeField(blank = True, null = True, db_index = True)

    objects = LockingManager()

    def __unicode__(self):
        return self.song.title

    def yt_timeoffset(self):
        """
        Return current YouTube time offset
        """
        if self.song.song_length == None or not self.played:
            return 0
        left = self.timeleft()
        if left < 1:
            return -1
        offset = self.song.song_length + self.song.get_metadata().ytvidoffset - left
        return offset

    def timeleft(self):
        """
        Return in seconds the time until song is finished playing
        """
        if self.song.song_length == None or not self.played or not self.time_played:
            return 0
        delta = datetime.datetime.now() - self.time_played
        return self.song.song_length - delta.seconds

    def get_eta(self):
        """
        Find when song will play, according to current queue
        """
        if self.id:
            baseq = Queue.objects.filter(played=False).exclude(id=self.id)
            baseq_lt = Queue.objects.filter(played=False, id__lt=self.id)
        else:
            baseq = baseq_lt = Queue.objects.filter(played=False)
        try :
            timelimit = datetime.datetime.now() - datetime.timedelta(hours=6)
            playtime = Queue.objects.select_related(depth=2).filter(played=True).filter(time_played__gt = timelimit ).order_by('-time_played')[0].timeleft()
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
        """
        Store expected time to play to the object.
        """
        self.eta = self.get_eta()

class SongComment(models.Model):
    song = models.ForeignKey(Song)
    user = models.ForeignKey(User)
    comment = models.TextField()
    staff_comment = models.BooleanField(default=False, verbose_name = "Staff only")
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
    added = models.DateTimeField(auto_now_add=True, db_index=True)
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
    reply_to = models.ForeignKey('self', blank = True, null = True, default = None)
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

    def has_unread(self):
        return self.privatemessage_set.filter(unread=True).exists()

    def save(self, *args, **kwargs):
        #Find the grandparent message
        if self.reply_to:
            ref = self.reply_to.reply_to
            while ref.reply_to:
                ref = ref.reply_to
            self.reply_to = ref

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

    def log(self, user, message):
        return ObjectLog.objects.create(obj=self, user=user, text=message)

    def get_logs(self):
        obj_type = ContentType.objects.get_for_model(self)
        return ObjectLog.objects.filter(content_type__pk=obj_type.id, object_id=self.id)

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

class SongLicense(models.Model):
    name = models.CharField(max_length=50, verbose_name="Name")
    description = models.TextField(verbose_name="Description", blank = True)
    icon = models.ImageField(upload_to = 'media/license', blank = True, null = True, verbose_name="License icon")
    url = models.URLField(unique = True, verbose_name="License URL", blank = True)
    downloadable = models.BooleanField(default=False, verbose_name="Can be downloaded")

    @models.permalink
    def get_absolute_url(self):
        return ("dv-license", [str(self.id)])

    def __unicode__(self):
        return self.name


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
    """
    Create profile entry for new user

    Post-save hook for User model
    """
    if kwargs["created"]:
        try:
            profile = Userprofile(user = kwargs["instance"])
            profile.save()
        except:
            pass
post_save.connect(create_profile, sender=User)

def set_song_values(sender, **kwargs):
    song = kwargs["instance"]
    if (not song.song_length) and song.status != 'K' and os.path.isfile(song.file.path):
        try:
            song.set_song_data()
        except:
            song.status = 'K'
        if not song.song_length:
            song.status = 'K'
        song.save()
post_save.connect(set_song_values, sender = Song)

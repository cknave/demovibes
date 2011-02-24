from webview.models import *
from webview.forms import *
from webview import common

from openid_provider.models import TrustedRoot

from mybaseview import MyBaseView

from tagging.models import TaggedItem
import tagging.utils

from django.utils.translation import ugettext as _

from django import forms
from django.http import HttpResponseRedirect, HttpResponseNotFound, HttpResponseBadRequest, HttpResponse

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import logout
from django.shortcuts import get_object_or_404, redirect
from django.template import TemplateDoesNotExist
from django.conf import settings
from django.views.generic.simple import direct_to_template

from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.core.files.base import File
from django.core.cache import cache

from django.views.decorators.cache import cache_page
from django.contrib.contenttypes.models import ContentType

from random import choice
import logging

from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_protect

import j2shim

import hashlib
import time
import mimetypes
import os
import re
import random
# Create your views here.

L = logging.getLogger('webview.views')

class WebView(MyBaseView):
    basetemplate = "webview/"

class SongView(WebView):

    def initialize(self):
        songid = self.kwargs['song_id']
        self.context['song'] = self.song = get_object_or_404(Song, id=songid)

class ProfileView(WebView):
    def initialize(self):
        username = self.kwargs['user']
        self.user = get_object_or_404(User, username = username)
        self.profile = common.get_profile(self.user)

    def check_permissions(self):
        return self.profile.viewable_by(self.request.user)

class ListByLetter(WebView):
    """
    List a model by letter, if given.

    Model need to have "startswith" and letter var need to be "letter"
    """
    model = None

    def initialize(self):
        letter = self.kwargs.get("letter", False)
        if letter and not letter in alphalist or letter == '-':
            letter = '#'
        self.letter = letter
        self.context['letter'] = letter
        self.context['al'] = alphalist

    def set_context(self):
        if self.model:
            if self.letter:
                results = self.model.objects.filter(startswith=self.letter)
            else:
                results = self.model.objects.all()
            return {'object_list': results }
        return {}

#-------------------------------------------------------

class PlaySong(SongView):
    template="playsong.html"
    staff_required = True

    def set_context(self):
        return {'song': self.song}

class AddCompilation(WebView):
    template = "add_compilation.html"
    login_required = True
    forms = [
        (CreateCompilationForm, "compform"),
    ]

    def pre_view(self):
        self.context['songsinput']=""

    def save_compilation(self, compdata, songs):
        newcf = compdata.save(commit=False)
        if not newcf.id:
            newcf.created_by = self.request.user
            newcf.status = "U"
        newcf.save()
        compdata.save_m2m()

        artists = []
        playtime = 0
        newcf.reset_songs()
        for index, S in enumerate(songs):
            newcf.add_song(S, index)
            playtime = playtime + S.song_length
            for a in S.get_metadata().artists.all():
                if a not in artists:
                    artists.append(a)
        newcf.running_time = playtime
        newcf.prod_artists.clear()
        for a in artists:
            newcf.prod_artists.add(a)
        newcf.save()
        return newcf

    def POST(self):
        songstr = self.request.POST.get("songsinput", "").split(",")
        self.context['songsinput'] = self.request.POST.get("songsinput", "")
        songs = []
        if songstr:
            for S in songstr:
				# By default songsinput is empty but in fact we have one entry in list (u'')
				# So the code will goes here ... but not valid S
				if S:
					songs.append(Song.objects.get(id=S))

        if self.forms_valid and songs:
            newcf = self.save_compilation(self.context["compform"], songs)
            self.redirect(newcf)

#Borks for some weird reason... Not done
class EditCompilation(AddCompilation):
    staff_required = True

    def form_compform_init(self):
        ci = self.kwargs.get("comp_id")
        self.c = Compilation.objects.get(id=ci)
        return {'instance': self.c}

    def post_view(self):
        if not self.context['songsinput']:
            songs = self.c.get_songs()
            self.context['songsinput'] = ','.join([ str(s.id) for s in songs ])

def about_pages(request, page):
    try:
        return direct_to_template(request, template="about/%s.html" % page)
    except TemplateDoesNotExist:
        return HttpResponseNotFound()

@login_required
def inbox(request):
    pms = request.GET.get('type','')
    delete = request.GET.get('delete','')
    if delete:
        try:
            delpm = int(delete)
            pm = PrivateMessage.objects.get(pk = delpm, to = request.user)
        except:
            return HttpResponseNotFound()
        pm.visible = False
        pm.save()
    if pms == "sent":
        mails = PrivateMessage.objects.filter(sender = request.user, visible = True)
    else:
        pms = "received" #to remove injects
        mails = PrivateMessage.objects.filter(to = request.user, visible = True)
    return j2shim.r2r('webview/inbox.html', {'mails' : mails, 'pms': pms}, request=request)

@login_required
def read_pm(request, pm_id):
    pm = get_object_or_404(PrivateMessage, id = pm_id)
    if pm.to == request.user:
        pm.unread = False
        pm.save()
        return j2shim.r2r('webview/view_pm.html', {'pm' : pm}, request=request)
    if pm.sender == request.user:
        return j2shim.r2r('webview/view_pm.html', {'pm' : pm}, request=request)
    return HttpResponseRedirect(reverse('dv-inbox'))

@login_required
def send_pm(request):
    if request.method == 'POST':
        form = PmForm(request.POST)
        if form.is_valid():
            F = form.save(commit=False)
            F.sender=request.user
            F.save()
            return HttpResponseRedirect(reverse('dv-inbox'))
    else:
        title = request.GET.get('title', "")
        to = request.GET.get('to', "")
        try:
            U = User.objects.get(username=to)
        except:
            U = None
        form = PmForm(initial= {'to': U, 'subject' : title})
    return j2shim.r2r('webview/pm_send.html', {'form' : form}, request)

class AddQueue(SongView):
    """
    Add a song to the queue
    """
    template = "song_queued.html"
    login_required = True

    def GET(self):
        ref = self.request.META.get('HTTP_REFERER', False)
        url = self.song.get_absolute_url()
        if not self.request.is_ajax() and ref and not ref.endswith(url):
            return self.redirect(url)
        common.queue_song(self.song, self.request.user)
        if self.request.is_ajax():
            return HttpResponse("OK")

class addComment(SongView):
    """
    Add a comment to a song.
    """
    login_required = True

    def pre_view(self):
        self.redirect(self.song)

    def POST(self):
        comment = self.request.POST.get("Comment", "").strip()
        if comment:
            SongComment.objects.create(comment = comment, song = self.song, user = self.request.user)

def site_about(request):
    """
    Support for a generic 'About' function
    """
    return j2shim.r2r('webview/site-about.html', { }, request)

def chat(request):
    """
    	Support for a generic 'chat' page
    """
    return j2shim.r2r('webview/chat.html', { }, request)
 

class listQueue(WebView):
    """
    Display the current song, the next songs in queue, and the latest 20 songs in history.
    """
    template = "queue_list.html"

    def set_context(self):
        return {
                'now_playing': "",
                'history': common.get_history(),
                'queue': common.get_queue(),
        }

def list_song(request, song_id):
    song = get_object_or_404(Song, id=song_id)

    # We can now get any compilation data that this song is a part of
    comps = Compilation.objects.filter(songs__id = song.id)

    # Has this song been remixed?
    remix_list = SongMetaData.objects.filter(remix_of_id = song.id, active=True)
    remix = [d.song for d in remix_list]
    related = Song.tagged.related_to(song)
    tags = song.tags
    t2 = []
    for tag in tags:
        tag.count = tag.items.count()
        t2.append(tag)
    tags = tagging.utils.calculate_cloud(t2)

    return j2shim.r2r('webview/song_detail.html', \
        { 'object' : song, 'vote_range': [1, 2, 3, 4, 5], 'comps' : comps, 'remix' : remix, 'related': related, 'tags': tags }\
        , request)

class ViewUserFavs(ProfileView):
    """
    List the favorites of a user
    """
    template = "user_favorites.html"

    def set_context(self):
        favorites = Favorite.objects.filter(user = self.user)
        return {'favorites':favorites, 'favuser': self.user}

class MyProfile(WebView):
    template = "my_profile.html"
    login_required = True
    forms = [(ProfileForm, "form")]

    def initialize(self):
        self.profile = common.get_profile(self.request.user)
        self.links = LinkCheck("U", object = self.profile)

    def pre_view(self):
        rootid = self.request.REQUEST.get("killroot", False)
        if rootid and rootid.isdigit():
            root = TrustedRoot.objects.get(id=rootid)
            if root.openid.user == self.request.user:
                root.delete()
                return self.redirect("dv-my_profile")

    def POST(self):
        if self.forms_valid and self.links.is_valid(self.request.POST):
            self.context['form'].save()
            self.links.save(self.profile)
            self.redirect("dv-my_profile")

    def form_form_init(self):
        return {'instance': self.profile}

    def set_context(self):
        return {'profile': self.profile, 'links': self.links}


class ViewProfile(ProfileView):
    """
    View a user's profile
    """
    template = "view_profile.html"

    def set_context(self):
        return {'profile': self.profile}

def search(request):
    """
    Return the first 40 matches of songs, artists and groups.
    """
    if request.method == 'POST' and "Search" in request.POST:
        searchterm = request.POST['Search']
        result_limit = getattr(settings, 'SEARCH_LIMIT', 40)
        if settings.USE_FULLTEXT_SEARCH == True:
            users = User.objects.filter(username__search = searchterm)[:result_limit]
            songs = Song.objects.select_related(depth=1).filter(title__search = searchterm)[:result_limit]
            artists = Artist.objects.filter(handle__search = searchterm)|Artist.objects.filter(name__search = searchterm)[:result_limit]
            groups = Group.objects.filter(name__search = searchterm)[:result_limit]
            compilations = Compilation.objects.filter(name__search = searchterm)[:result_limit]
            labels = Label.objects.filter(name__search = searchterm)[:result_limit]
        else:
            users = User.objects.filter(username__icontains = searchterm)[:result_limit]
            songs = Song.objects.select_related(depth=1).filter(title__icontains = searchterm)[:result_limit]
            artists = Artist.objects.filter(handle__icontains = searchterm)|Artist.objects.filter(name__icontains = searchterm)[:result_limit]
            groups = Group.objects.filter(name__icontains = searchterm)[:result_limit]
            compilations = Compilation.objects.filter(name__icontains = searchterm)[:result_limit]
            labels = Label.objects.filter(name__icontains = searchterm)[:result_limit]


        return j2shim.r2r('webview/search.html', \
            { 'songs' : songs, 'artists' : artists, 'groups' : groups, 'users' : users, 'compilations' : compilations, 'labels' : labels }, \
            request=request)
    return j2shim.r2r('webview/search.html', {}, request=request)

def show_approvals(request):
    """
    Shows the most recently approved songs in it's own window
    """
    result_limit = getattr(settings, 'UPLOADED_SONG_COUNT', 150)
    songs = SongApprovals.objects.order_by('-id')[:result_limit]

    return j2shim.r2r('webview/recent_approvals.html', { 'songs': songs , 'settings' : settings }, request=request)

class ListArtists(ListByLetter):
    template = "artist_list.html"
    model = Artist

class ListGroups(ListByLetter):
    template = "group_list.html"
    model = Group

class ListLabels(ListByLetter):
    template = "label_list.html"
    model = Label

class ListComilations(ListByLetter):
    template = "compilation_list.html"
    model = Compilation

class ListSongs(ListByLetter):
    template = "song_list.html"
    model = Song

@login_required
def log_out(request):
    """
    Show a user a form, and then logs user out if a form is sent in to that address.
    """
    if request.method == 'POST':
        logout(request)
        return HttpResponseRedirect("/")
    return j2shim.r2r('webview/logout.html', {}, request=request)

class songHistory(SongView):
    """
    List queue history of song
    """
    template = "song_history.html"
    def set_context(self):
        return {'requests': self.song.queue_set.all()}

class songVotes(SongView):
    """
    List vote history of song
    """
    template = "song_votes.html"
    def set_context(self):
        return {'votelist': self.song.songvote_set.all()}

class songComments(SongView):
    """
    List the comments belonging to a song
    """
    template = "song_comments.html"
    def set_context(self):
        return {'commentlist': self.song.songcomment_set.all()}

def view_compilation(request, comp_id):
    """
    Try to view a compilation entry.
    """
    permission = request.user.has_perm("webview.make_session")
    comp = get_object_or_404(Compilation, id=comp_id) # Find it, or return a 404 error
    if permission:
        sessionform = CreateSessionForm()
    else:
        sessionform = False
    if request.method == "POST" and permission:
        sessionform = CreateSessionForm(request.POST)
        if sessionform.is_valid():
            desc = sessionform.cleaned_data['description']
            playtime = sessionform.cleaned_data['time']
            for song in comp.get_songs():
                Queue.objects.create(song=song, played=False, playtime=playtime, requested_by = request.user, description = desc)
            common.get_queue(True)
            return redirect("dv-queue")
    return j2shim.r2r('webview/compilation.html',
        { 'comp' : comp, 'user' : request.user , 'sessionform': sessionform},
        request=request)

@login_required
def add_favorite(request, id): # XXX Fix to POST
    """
    Add a song to the user's favorite. Takes one argument, song id.
    """
    user = request.user
    song = get_object_or_404(Song, id=id)
    Q = Favorite.objects.filter(user = user, song = song)
    if not Q: # Does the user already have this as favorite?
        f = Favorite(user=user, song=song)
        f.save()
    #return HttpResponseRedirect(reverse('dv-favorites'))
    refer = 'HTTP_REFERER' in request.META and request.META['HTTP_REFERER'] or False
    return HttpResponseRedirect(refer or reverse("dv-favorites"))

def oneliner(request):
    oneliner = Oneliner.objects.select_related(depth=1).order_by('-id')[:20]
    return j2shim.r2r('webview/oneliner.html', {'oneliner' : oneliner}, \
        request=request)

@login_required
def oneliner_submit(request):
    """
    Add a text line to the oneliner.
    Returns user to referrer position, or to /
    """
    message =  request.POST['Line'].strip()
    common.add_oneliner(request.user, message)
    try:
        refer = request.META['HTTP_REFERER']
        return HttpResponseRedirect(refer)
    except:
        return HttpResponseRedirect("/")

@login_required
def list_favorites(request):
    """
    Display a user's favorites.
    """
    user = request.user
    songs = Favorite.objects.filter(user=user)

    try:
        user_profile = Userprofile.objects.get(user = user)
        use_pages = user_profile.paginate_favorites
    except:
        # In the event it bails, revert to pages hehe
        use_pages = True

    if(use_pages):
        paginator = Paginator(songs, settings.PAGINATE)
        page = int(request.GET.get('page', '1'))
        try:
            songlist = paginator.page(page)
        except (EmptyPage, InvalidPage):
            songlist = paginator.page(paginator.num_pages)
        return j2shim.r2r('webview/favorites.html', \
          {'songs': songlist.object_list, 'page' : page, 'page_range' : paginator.page_range}, \
          request=request)

    # Attempt to list all faves at once!
    return j2shim.r2r('webview/favorites.html', { 'songs': songs }, request=request)

@login_required
def del_favorite(request, id): # XXX Fix to POST
    """
    Removes a favorite from the user's list.
    """
    S = Song.objects.get(id=id)
    Q = Favorite.objects.filter(user = request.user, song = S)
    if Q:
        Q[0].delete()
    try:
        refer = request.META['HTTP_REFERER']
        return HttpResponseRedirect(refer)
    except:
        return HttpResponseRedirect(reverse('dv-favorites'))

class LinkCheck(object):
    def __init__(self, linktype, object = None, status = 0, user = None, add=False):
        self.type = linktype
        self.add = add
        self.verified = []
        self.user = user
        self.status = status
        self.object = object
        self.valid = False
        self.get_list()
        self.title = "External Resources"

    def get_link_for(self, o, generic):
        if not o or not generic:
            return None
        bla = ContentType.objects.get_for_model(o)
        r = GenericLink.objects.filter(content_type__pk=bla.id, object_id=o.id, link=generic)
        return r and r[0] or None

    def get_list(self):
        self.linklist = GenericBaseLink.objects.filter(linktype = self.type)
        r = []
        for x in self.linklist:
            val = self.get_link_for(self.object, x)
            value=val and val.value or ""
            r.append({'link': x, 'value': value, "error": "", "comment": ""})
        self.links = r
        return self.linklist

    def __unicode__(self):
        return self.as_table()

    def as_table(self):
        """
        Print links form as table
        """
        return j2shim.r2s('webview/t/linksform.html', \
            {'links': self.links, 'title': self.title })

    def is_valid(self, postdict):
        """
        Check if given links are valid according to given regex
        """
        self.valid = True
        for entry in self.links:
            l = entry['link'] # GenericBaseLink object
            key = "LL_%s" % l.id
            if postdict.has_key(key):
                val = postdict[key].strip()
                if val:
                    ckey = key+"_comment"
                    comment = postdict.has_key(ckey) and postdict[ckey].strip() or ""

                    #Fill out dict in case it needs to be returned to user
                    entry['value'] = val
                    entry['comment'] = comment

                    if re.match(l.regex + "$", val):
                        self.verified.append((l, val, comment)) #Add to approved list
                    else:
                        self.valid = False
                        entry['error'] = "The input did not match expected value"
                else:
                    self.verified.append((l, "", "")) #No value for this link
        return self.valid

    def save(self, obj):
        """
        Save links to database
        """
        if self.verified and self.valid:
            for l, val, comment in self.verified:
                r = self.get_link_for(obj, l)
                if val:

                    if r and not self.add:
                        r.value = val
                        r.save()
                    else:
                        GenericLink.objects.create(
                            content_object=obj,
                            value=val,
                            link=l,
                            status = self.status,
                            comment = comment,
                            user = self.user
                        )
                else:
                    if r and not self.add:
                        r.delete()
            obj.save() # For caching

@permission_required('webview.change_songmetadata')
def new_songinfo_list(request):
    alink = request.GET.get("alink", False)
    status = request.GET.get("status", False)
    if alink and status.isdigit():
        link = get_object_or_404(GenericLink, id=alink)
        link.status = int(status)
        link.content_object.save()
        link.save()
    nusonginfo = SongMetaData.objects.filter(checked=False)
    nulinkinfo = GenericLink.objects.filter(status=1)
    c = {'metainfo': nusonginfo, 'linkinfo': nulinkinfo}
    return j2shim.r2r("webview/list_newsonginfo.html", c, request)

@permission_required('webview.change_songmetadata')
def list_songinfo_for_song(request, song_id):
    song = get_object_or_404(Song, id=song_id)
    metalist = SongMetaData.objects.filter(song=song)
    c = {'metalist':metalist, 'song': song}
    return j2shim.r2r("webview/list_songinfo.html", c, request)

@login_required
def add_songlinks(request, song_id):
    song = get_object_or_404(Song, id=song_id)
    links = LinkCheck("S", status=1, user = request.user, add = True)
    if request.method == "POST":
        if links.is_valid(request.POST):
            links.save(song)
            return redirect(song)
    c = {'song': song, 'links': links}
    return j2shim.r2r("webview/add_songlinks.html", c, request)


@permission_required('webview.change_songmetadata')
def view_songinfo(request, songinfo_id):
    meta = get_object_or_404(SongMetaData, id=songinfo_id)
    if request.method == "POST":
        if request.POST.has_key("activate") and request.POST["activate"]:
            if not meta.checked:
                meta.user.get_profile().send_message(
                    subject="Song info approved",
                    message="Your metadata for song [song]%s[/song] is now active :)"  % meta.song.id,
                    sender = request.user
                )
            meta.set_active()
        if request.POST.has_key("deactivate") and request.POST["deactivate"]:
            if not meta.checked:
                meta.user.get_profile().send_message(
                    subject="Song info not approved",
                    message="Your metadata for song [song]%s[/song] was not approved :(" % meta.song.id,
                    sender = request.user
                )
            meta.checked = True
            meta.save()
    c = {'meta': meta }
    return j2shim.r2r("webview/view_songinfo.html", c, request)

#Not done
class editSonginfo(SongView):
    template = "edit_songinfo.html"
    forms = [EditSongMetadataForm, "form"]
    login_required = True

    def form_form_init(self):
        if self.method == "POST":
            m = SongMetaData(song=self.song, user=request.user)
        else:
            m = self.song.get_metadata()
            m.comment = ""
        return {'instance': m}

    def POST(self):
        if self.forms_valid:
            self.context['form'].save()
            self.redirect(self.context['song'])

@login_required
def edit_songinfo(request, song_id):
    song = get_object_or_404(Song, id=song_id)
    meta = song.get_metadata()
    meta.comment = ""

    if request.method == "POST":
        m = SongMetaData(song=song, user=request.user)
        form = EditSongMetadataForm(request.POST, instance=m)
        if form.is_valid():
            d=form.save()
            return redirect(song)
    else:
        form = EditSongMetadataForm(instance=meta)

    c = {'form': form, 'song': song}
    return j2shim.r2r("webview/edit_songinfo.html", c, request)

@login_required
def upload_song(request, artist_id):
    artist = get_object_or_404(Artist, id=artist_id)
    auto_approve = getattr(settings, 'ADMIN_AUTO_APPROVE_UPLOADS', 0)
    artist_auto_approve = getattr(settings, 'ARTIST_AUTO_APPROVE_UPLOADS', 1)

    links = LinkCheck("S", user = request.user)

    # Quick test to see if the artist is currently active. If not, bounce
    # To the current queue!
    if artist.status != 'A':
        return HttpResponseRedirect(reverse('dv-queue'))

    if request.method == 'POST':
        if artist_auto_approve and artist.link_to_user == request.user:
            # Auto Approved Song. Set Active, Add to Recent Uploads list
            status = 'A'
        else:
            status = 'U'

        # Check to see if moderation settings allow for the check
        if request.user.is_staff and auto_approve == 1:
            # Automatically approved due to Moderator status
            status = 'A'

        a = Song(uploader = request.user, status = status)

        form = UploadForm(request.POST, request.FILES, instance = a)
        infoform = SongMetadataForm(request.POST)

        if links.is_valid(request.POST) and form.is_valid() and infoform.is_valid():
            new_song = form.save(commit=False)
            new_song.save()

            songinfo = infoform.save(commit=False)
            songinfo.user = request.user
            songinfo.song = new_song
            songinfo.checked = True
            songinfo.save()

            infoform.save_m2m()
            form.save_m2m()

            songinfo.artists.add(artist)

            songinfo.set_active()

            links.save(new_song)

            if(new_song.status == 'A'):
                # Auto Approved!
                try:
                    # If the song entry exists, we shouldn't care
                    exist = SongApprovals.objects.get(song = new_song)

                except:
                    # Should throw when the song isn't found in the DB
                    Q = SongApprovals(song = new_song, approved_by=request.user, uploaded_by=request.user)
                    Q.save()

            return HttpResponseRedirect(new_song.get_absolute_url())
    else:
        form = UploadForm()
        infoform = SongMetadataForm()
    return j2shim.r2r('webview/upload.html', \
        {'form' : form, 'infoform': infoform, 'artist' : artist, 'links': links }, \
        request=request)

@permission_required('webview.change_song')
def activate_upload(request):
    if "song" in request.GET and "status" in request.GET:
        songid = int(request.GET['song'])
        status = request.GET['status']
        song = Song.objects.get(id=songid)

        if status == 'A':
            stat = "Accepted"
            song.status = "A"
        if status == 'R':
            stat = "Rejected"
            song.status = 'R'

        # This used to be propriatary, it is now a template. AAK
        mail_tpl = loader.get_template('webview/email/song_approval.txt')
        c = Context({
                'songid' : songid,
                'site' : Site.objects.get_current(),
                'stat' : stat,
        })
        song.save()

        # Only add if song is approved! Modified to check to see if song exists first!
        # There is probbably a better way of doing this crude check! AAK
        if(status == 'A'):
            try:
                # If the song entry exists, we shouldn't care
                exist = SongApprovals.objects.get(song = song)

            except:
                # Should throw when the song isn't found in the DB
                Q = SongApprovals(song=song, approved_by=request.user, uploaded_by=song.uploader)
                Q.save()

        if song.uploader.get_profile().pm_accepted_upload and status == 'A' or status == 'R':
            song.uploader.get_profile().send_message(
                sender = request.user,
                message = mail_tpl.render(c),
                subject = "Song Upload Status Changed To: %s" % stat
            )
    songs = Song.objects.filter(status = "U").order_by('added')
    return j2shim.r2r('webview/uploaded_songs.html', {'songs' : songs}, request=request)

class songStatistics(WebView):
    template = "stat_songs.html"

    def list_favorites(self):
        return Song.objects.order_by('-num_favorited')

    def list_voted(self):
        return Song.objects.filter(rating_votes__gt = 9).order_by('-rating')

    def list_leastvotes(self):
		return Song.objects.filter(status="A").exclude(locked_until__gte=datetime.datetime.now()).order_by('rating_votes', '?')[:100]
		
    def list_random(self):
		max_id = Song.objects.order_by('-id')[0].id 
		max_songs = Song.objects.filter(status="A").count() 
		num_songs = 100 
		num_songs = num_songs < max_songs and num_songs or max_songs 
		songlist = [] 
		r_done = [] 
		r = random.randint(0, max_id+1) 
		while len(songlist) < num_songs: 
		  r_list = [] 
		  curr_count = (num_songs - len(songlist) + 2)
		  for x in range(curr_count): 
			while r in r_done: 
			  r = random.randint(0, max_id+1) 
			r_list.append(r) 
		  r_done.extend(r_list) 
		  songlist.extend([s for s in Song.objects.filter(id__in=r_list, status="A")]) 
		return songlist

    def list_mostvotes(self):
        return Song.objects.order_by('-rating_votes')

    def list_queued2(self):
        return Song.objects.filter(status="A").exclude(locked_until__gte=datetime.datetime.now()).order_by('times_played', 'locked_until')

    def list_queued(self):
        return Song.objects.filter(status="A").order_by('-times_played')

    def initialize(self):
        self.stats = {
            'random': ("Random songs from the database!", "rating_votes", "# Votes", self.list_random),
            'leastvotes': ("Songs with the least number of votes in the database.", "rating_votes", "# Votes", self.list_leastvotes),
            'favorites': ("Songs which appear on more users favourites lists.", "num_favorited", "# Favorited", self.list_favorites),
            'voted': ("Songs with the highest ratings in the database.", "rating", "Rating", self.list_voted),
            'queued': ("The most played songs in the database.", "times_played", "# Played", self.list_queued),
            'unplayed': ("The least played songs in the database.", "times_played", "# Played", self.list_queued2),
            'mostvotes': ("Songs with the highest number of votes cast.", "rating_votes", "# Votes", self.list_mostvotes),
        }
        self.stattype = self.kwargs.get("stattype", "")

    def set_context(self):
        if self.stattype in self.stats.keys():
            title, stat, name, songs = self.stats[self.stattype]
            return {'songs': songs()[:100], 'title': title, 'numsongs': 100, 'stat': stat, 'name': name}
        self.template = "stat_songs_index.html"
        return {'keys': self.stats}

class tagCloud(WebView):
    template = "tag_cloud.html"
    cache_key = "tag_cloud"
    cache_duration = 24*60*60

    def get_cache_key(self):
        tag_id = cache.get("tagver", 0)
        key = "tag_cloud_%s" % tag_id
        return key

    def set_cached_context(self):
        min_count = getattr(settings, 'TAG_CLOUD_MIN_COUNT', 1)
        tags = Song.tags.cloud(min_count=min_count)
        return {'tags': tags}

class tagDetail(WebView):
    template = "tag_detail.html"
    cache_duration = 24*60*60

    def get_cache_key(self):
        tag_id = cache.get("tagver", 0)
        key = "tagdetail_%s_%s" % (self.kwargs.get("tag", ""), tag_id)
        return hashlib.md5(key).hexdigest()

    def set_cached_context(self):
        tag = self.kwargs.get("tag", "")
        songs = TaggedItem.objects.get_by_model(Song, tag)
        related = Song.tags.related(tag, counts=True)
        related = tagging.utils.calculate_cloud(related)
        c = {'songs': songs, 'related': related, 'tag':tag}
        return c

class tagEdit(SongView):
    login_required=True
    template = "tag_edit.html"

    def POST(self):
        t = self.request.POST.get('tags', "")
        self.song.tags = re.sub(r'[^a-zA-Z0-9!_\-?& ]+', '', t)
        self.song.save() # For updating the "last changed" value
        TagHistory.objects.create(user=self.request.user, song=self.song, tags = self.request.POST['tags'])
        try:
            cache.incr("tagver")
        except:
            cache.set("tagver", 1)
        return self.redirect(self.song)

    def set_context(self):
        tags = tagging.utils.edit_string_for_tags(self.song.tags)
        changes = TagHistory.objects.filter(song=self.song).order_by('-id')[:5]
        return {'tags': tags, 'changes': changes}

@login_required
def create_artist(request):
    """
    Simple form to allow registereed users to create a new artist entry.
    """
    auto_approve = getattr(settings, 'ADMIN_AUTO_APPROVE_ARTIST', 0)

    links = LinkCheck("A")

    if request.method == 'POST':
        # Check to see if moderation settings allow for the check
        if request.user.is_staff and auto_approve == 1:
            # Automatically approved due to Moderator status
            status = 'A'
        else:
            status = 'U'

        a = Artist(created_by = request.user, status = status)
        form = CreateArtistForm(request.POST, request.FILES, instance = a)
        if form.is_valid() and links.is_valid(request.POST):
            new_artist = form.save(commit=False)
            new_artist.save()
            form.save_m2m()

            links.save(new_artist)

            return HttpResponseRedirect(new_artist.get_absolute_url())
    else:
        form = CreateArtistForm()
    return j2shim.r2r('webview/create_artist.html', \
        {'form' : form, 'links': links }, \
        request=request)

@permission_required('webview.change_artist')
def activate_artists(request):
    """
    Shows the most recently added artists who have a 'U' status in their upload marker
    """
    if "artist" in request.GET and "status" in request.GET:
        artistid = int(request.GET['artist'])
        status = request.GET['status']
        artist = Artist.objects.get(id=artistid)

        if status == 'A':
            stat = "Accepted"
            artist.status = "A"
        if status == 'R':
            stat = "Rejected"
            artist.status = 'R'

        # Prepare a mail template to inform user of the status of their request
        mail_tpl = loader.get_template('webview/email/artist_approval.txt')
        c = Context({
                'artist' : artist,
                'site' : Site.objects.get_current(),
                'stat' : stat,
        })
        artist.save()

        # Send the email to inform the user of their request status

        if artist.created_by.get_profile().email_on_artist_add and status == 'A' or status == 'R':
            artist.created_by.get_profile().send_message(sender = request.user,
                message = mail_tpl.render(c),
                subject = u"Artist %s : %s" % (artist.handle, stat)
            )

    artists = Artist.objects.filter(status = "U").order_by('last_updated')
    return j2shim.r2r('webview/pending_artists.html', { 'artists': artists }, request=request)

@login_required
def create_group(request):
    """
    Simple form to allow registereed users to create a new group entry.
    """
    auto_approve = getattr(settings, 'ADMIN_AUTO_APPROVE_GROUP', 0)

    links = LinkCheck("G")

    if request.method == 'POST':
        # Check to see if moderation settings allow for the check
        if request.user.is_staff and auto_approve == 1:
            # Automatically approved due to Moderator status
            status = 'A'
        else:
            status = 'U'

    if request.method == 'POST':
        g = Group(created_by = request.user, status = status)
        form = CreateGroupForm(request.POST, request.FILES, instance = g)
        if form.is_valid() and links.is_valid(request.POST):
            new_group = form.save(commit=False)
            new_group.save()
            form.save_m2m()

            links.save(new_group)

            return HttpResponseRedirect(new_group.get_absolute_url())
    else:
        form = CreateGroupForm()
    return j2shim.r2r('webview/create_group.html', \
        {'form' : form, 'links': links }, \
        request=request)

@permission_required('webview.change_group')
def activate_groups(request):
    """
    Shows the most recently added groups who have a 'U' status in their upload marker
    """
    if "group" in request.GET and "status" in request.GET:
        groupid = int(request.GET['group'])
        status = request.GET['status']
        group = Group.objects.get(id=groupid)

        if status == 'A':
            stat = "Accepted"
            group.status = "A"
        if status == 'R':
            stat = "Rejected"
            group.status = 'R'

        # Prepare a mail template to inform user of the status of their request
        mail_tpl = loader.get_template('webview/email/group_approval.txt')
        c = Context({
                'group' : group,
                'site' : Site.objects.get_current(),
                'stat' : stat,
        })
        group.save()

        # Send the email to inform the user of their request status
        if group.created_by.get_profile().email_on_group_add and status == 'A' or status == 'R':
            group.created_by.get_profile().send_message(
                sender = request.user,
                message = mail_tpl.render(c),
                subject = "Group Request Status Changed To: %s" % stat
            )

    groups =Group.objects.filter(status = "U").order_by('last_updated')
    return j2shim.r2r('webview/pending_groups.html', { 'groups': groups }, request=request)

@login_required
def create_label(request):
    """
    Simple form to allow registereed users to create a new label entry.
    """
    auto_approve = getattr(settings, 'ADMIN_AUTO_APPROVE_LABEL', 0)

    links = LinkCheck("L")

    if request.method == 'POST':
        # Check to see if moderation settings allow for the check
        if request.user.is_staff and auto_approve == 1:
            # Automatically approved due to Moderator status
            status = 'A'
        else:
            status = 'U'

    if request.method == 'POST':
        l = Label(created_by = request.user, status = status)
        form = CreateLabelForm(request.POST, request.FILES, instance = l)
        if form.is_valid() and links.is_valid(request.POST):
            new_label = form.save(commit=False)
            new_label.save()
            form.save_m2m()

            links.save(new_label)

            return HttpResponseRedirect(new_label.get_absolute_url())
    else:
        form = CreateLabelForm()
    return j2shim.r2r('webview/create_label.html', \
        {'form' : form, 'links': links }, \
        request=request)

@permission_required('webview.change_label')
def activate_labels(request):
    """
    Shows the most recently added labels who have a 'U' status in their upload marker
    """
    if "label" in request.GET and "status" in request.GET:
        labelid = int(request.GET['label'])
        status = request.GET['status']
        this_label = Label.objects.get(id=labelid)

        if status == 'A':
            stat = "Accepted"
            this_label.status = "A"
        if status == 'R':
            stat = "Rejected"
            this_label.status = 'R'

        # Prepare a mail template to inform user of the status of their request
        mail_tpl = loader.get_template('webview/email/label_approval.txt')
        c = Context({
                'label' : this_label,
                'site' : Site.objects.get_current(),
                'stat' : stat,
        })
        this_label.save()

        # Send the email to inform the user of their request status
        if this_label.created_by.get_profile().email_on_group_add and status == 'A' or status == 'R':
            this_label.created_by.get_profile().send_message(
                sender = request.user,
                message = mail_tpl.render(c),
                subject = "Label Request Status Changed To: %s" % stat
            )

    labels = Label.objects.filter(status = "U").order_by('last_updated')
    return j2shim.r2r('webview/pending_labels.html', { 'labels': labels }, request=request)

def users_online(request):
    timefrom = datetime.datetime.now() - datetime.timedelta(minutes=5)
    userlist = Userprofile.objects.filter(last_activity__gt=timefrom).order_by('user__username')
    return j2shim.r2r('webview/online_users.html', {'userlist' : userlist}, request=request)

@login_required
def set_rating_autovote(request, song_id, user_rating):
    """
    Set a user's rating on a song. From 0 to 5
    """
    int_vote = int(user_rating)
    if int_vote <= 5 and int_vote > 0:
        S = Song.objects.get(id = song_id)
        S.set_vote(int_vote, request.user)
        #add_event(event="nowplaying")

        # Successful vote placed.
        try:
            refer = request.META['HTTP_REFERER']
            return HttpResponseRedirect(refer)
        except:
            return HttpResponseRedirect("/")

    # If the user tries any funny business, we redirect to the queue. No messing!
    return HttpResponseRedirect(reverse("dv-queue"))

@login_required
def set_rating(request, song_id):
    """
    Set a user's rating on a song. From 0 to 5
    """
    if request.method == 'POST':
        try:
            R = int(request.POST['Rating'])
        except:
             return HttpResponseRedirect(reverse('dv-song', args=[song_id]))
        if R <= 5 and R >= 1:
            S = Song.objects.get(id = song_id)
            S.set_vote(R, request.user)
    return HttpResponseRedirect(S.get_absolute_url())

def link_category(request, slug):
    """
    View all links associated with a specific link category slug
    """
    link_cat = get_object_or_404(LinkCategory, id_slug = slug)
    link_data_txt = Link.objects.filter(status="A").filter(link_type="T").filter(url_cat=link_cat) # See what linkage data we have
    return j2shim.r2r('webview/links_category.html', \
            {'links_txt' : link_data_txt, 'cat' : link_cat}, \
            request=request)

@login_required
def link_create(request):
    """
    User submitted links appear using this form for moderators to approve. Once sent, they are directed to
    A generic 'Thanks' page.
    """
    auto_approve = getattr(settings, 'ADMIN_AUTO_APPROVE_LINK', 0)

    if request.method == 'POST':
        # Check to see if moderation settings allow for the check
        if request.user.is_staff and auto_approve == 1:
            # Automatically approved due to Moderator status
            status = 'A'
        else:
            status = 'P'

        l = Link(submitted_by = request.user, status = status)
        form = CreateLinkForm(request.POST, request.FILES, instance = l)
        if form.is_valid():
            new_link = form.save(commit=False)
            new_link.save()
            form.save_m2m()
            return j2shim.r2r('webview/link_added.html', request=request) # Redirect to 'Thanks!' screen!
    else:
        form = CreateLinkForm()
    return j2shim.r2r('webview/create_link.html', { 'form' : form }, request=request)

@permission_required('webview.change_link')
def activate_links(request):
    """
    Show all currently pending links in the system. Only the l33t may access.
    """
    if "link" in request.GET and "status" in request.GET:
        linkid = int(request.GET['link'])
        status = request.GET['status']
        this_link = Link.objects.get(id=linkid)

        if status == 'A':
            this_link.status = "A"
            this_link.approved_by = request.user
        if status == 'R':
            this_link.status = "R"
            this_link.approved_by = request.user

        # Save this to the DB
        this_link.save()

    #links = Link.objects.filter(status = "P")
    links_txt = Link.objects.filter(status="P").filter(link_type="T")
    #links_but = Link.objects.filter(status="P").filter(link_type="U")
    #links_ban = Link.objects.filter(status="P").filter(link_type="B")
    return j2shim.r2r('webview/pending_links.html', { 'text_links' : links_txt }, request=request)

def site_links(request):
    """
    Show all active links for this site
    """
    link_cats = LinkCategory.objects.all() # All categories in the system
    return j2shim.r2r('webview/site-links.html', { 'link_cats' : link_cats }, request=request)

def memcached_status(request):
    try:
        import memcache
    except ImportError:
        return HttpResponseRedirect("/")

    if not (request.user.is_authenticated() and
            request.user.is_staff):
        return HttpResponseRedirect("/")

    # get first memcached URI
    m = re.match(
        "memcached://([.\w]+:\d+)", settings.CACHE_BACKEND
    )
    if not m:
        return HttpResponseRedirect("/")

    host = memcache._Host(m.group(1))
    host.connect()
    host.send_cmd("stats")

    class Stats:
        pass

    stats = Stats()

    while 1:
        line = host.readline().split(None, 2)
        if line[0] == "END":
            break
        stat, key, value = line
        try:
            # convert to native type, if possible
            value = int(value)
            if key == "uptime":
                value = datetime.timedelta(seconds=value)
            elif key == "time":
                value = datetime.datetime.fromtimestamp(value)
        except ValueError:
            pass
        setattr(stats, key, value)

    host.close_socket()

    return j2shim.r2r(
        'webview/memcached_status.html', dict(
            stats=stats,
            hit_rate=100 * stats.get_hits / stats.cmd_get,
            time=datetime.datetime.now(), # server time
        ), request=request)

class Login(MyBaseView):
    template="registration/login.html"

    MAX_FAILS_PER_HOUR = getattr(settings, "MAX_FAILED_LOGINS_PER_HOUR", 5)

    def pre_view(self):
        self.context['next'] = self.request.REQUEST.get("next", "")
        self.context['username'] = self.request.REQUEST.get("username", "")
        self.context['error'] = ""

    def check_limit(self, keys):
        for key in keys:
            if cache.get(key, 0) > self.MAX_FAILS_PER_HOUR:
                return True
        return False

    def add_to_limit(self, keys):
        for key in keys:
            if cache.get(key, None) == None:
                cache.set(key, 1, 60*60)
            else:
                cache.incr(key)

    def POST(self):
        ip = self.request.META.get("REMOTE_ADDR")
        username = self.request.POST['username']

        key1 = hashlib.md5("loginfail" + username).hexdigest()
        key2 = hashlib.md5("loginfail" + ip).hexdigest()
        if self.check_limit((key1, key2)):
            self.context['error'] = _("Too many failed logins. Please wait an hour before trying again.")
            return False

        password = self.request.POST['password']
        next = self.request.POST.get("next", False)
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(self.request, user)
                return self.redirect(next or 'dv-root')
            else:
                self.context['error'] = _(u"I'm sorry, your account have been disabled.")
        else:
            self.add_to_limit((key1, key2))
            self.context['error'] = _(u"I'm sorry, the username or password seem to be wrong.")

def upload_progress(request):
    """
    Return JSON object with information about the progress of an upload.
    """
    progress_id = ''
    if 'X-Progress-ID' in request.GET:
        progress_id = request.GET['X-Progress-ID']
    elif 'X-Progress-ID' in request.META:
        progress_id = request.META['X-Progress-ID']
    if progress_id:
        from django.utils import simplejson
        cache_key = "%s_%s" % (request.META['REMOTE_ADDR'], progress_id)
        data = cache.get(cache_key)
        return HttpResponse(simplejson.dumps(data))
    else:
        return HttpResponseServerError('Server Error: You must provide X-Progress-ID header or query param.')

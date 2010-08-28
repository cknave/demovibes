from webview.models import *
from webview.forms import *
from webview import common

from tagging.models import TaggedItem
import tagging.utils

from django import forms
from django.http import HttpResponseRedirect, HttpResponseNotFound, HttpResponseBadRequest, HttpResponse

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import logout
from django.shortcuts import get_object_or_404
from django.template import TemplateDoesNotExist
from django.conf import settings
from django.views.generic.simple import direct_to_template

from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.core.files.base import File
from django.core.cache import cache

from django.views.decorators.cache import cache_page

from random import choice

import j2shim

import time
#import mad
import mimetypes
import os
import re
# Create your views here.

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

@login_required
def addqueue(request, song_id): # XXX Fix to POST
    """
    Add a song to the playing queue.
    """
    try:
        song = Song.objects.get(id=song_id)
    except:
        return HttpResponseNotFound()
    #song.queue_by(request.user)
    common.queue_song(song, request.user)
    return direct_to_template(request, template = "webview/song_queued.html")

@login_required
def addcomment(request, song_id):
    """
    Add a comment to a song.
    """
    if request.method == 'POST':
        comment = request.POST['Comment'].strip()
        song = get_object_or_404(Song, id=song_id)
        if comment:
           form = SongComment(comment = request.POST['Comment'], song = song, user = request.user)
           form.save()
    return HttpResponseRedirect(song.get_absolute_url())

def site_about(request):
    """
    Support for a generic 'About' function
    """
    return j2shim.r2r('webview/site-about.html', { }, request)

def list_queue(request):
    """
    Display the current song, the next songs in queue, and the latest 20 songs in history.
    """
    now_playing = ""
    history = common.get_history()
    queue = common.get_queue()
    return j2shim.r2r('webview/queue_list.html', \
        {'now_playing': now_playing, 'history': history, 'queue': queue}\
        , request)
    
def list_song(request, song_id):
    song = get_object_or_404(Song, id=song_id)
    
    # We can now get any compilation data that this song is a part of
    comps = Compilation.objects.filter(songs__id = song.id)
    
    # Has this song been remixed?
    remix = Song.objects.filter(remix_of_id = song.id)
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

def view_user_favs(request, user):
    U = get_object_or_404(User, username = user)
    profile = common.get_profile(U)
    if not profile.viewable_by(request.user):
        return j2shim.r2r('base/error.html', { 'error' : "Sorry, you're not allowed to see this" }, request=request)
    favorites = Favorite.objects.filter(user = U)
    return j2shim.r2r('webview/user_favorites.html', \
        {'favorites' : favorites, 'favuser' : U}, \
        request=request)

@login_required
def my_profile(request):
    """
    Display the logged in user's profile.
    """
    user = request.user
    profile = common.get_profile(user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance = profile)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('dv-my_profile')) # To hinder re-post on refresh
    else:
        form = ProfileForm(instance=profile)
    return j2shim.r2r('webview/my_profile.html', {'profile' : profile, 'form' : form}, request=request)


def view_profile(request, user):
    """
    Display a user's profile.
    """
    ProfileUser = get_object_or_404(User,username = user)
    profile = common.get_profile(User.objects.get(username=user))
    if profile.viewable_by(request.user):
        return j2shim.r2r('webview/view_profile.html', \
            {'profile' : profile}, \
            request=request)
    return j2shim.r2r('base/error.html', { 'error' : "Sorry, you're not allowed to see this" }, request=request)

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
    songs = SongApprovals.objects.order_by('-approved')[:result_limit]
    
    return j2shim.r2r('webview/recent_approvals.html', { 'songs': songs , 'settings' : settings }, request=request)

def list_artists(request, letter):
    """
    List artists that start with a certain letter.
    """
    if not letter in alphalist or letter == '-':
        letter = '#'
    artists = Artist.objects.filter(startswith=letter)

    return j2shim.r2r('webview/artist_list.html', \
        {'object_list' : artists, 'letter' : letter, 'al': alphalist}, \
        request=request)

def list_groups(request, letter):
    """
    List groups that start with a certain letter.
    """
    if not letter in alphalist or letter == '-':
        letter = '#'
    groups = Group.objects.filter(startswith=letter).filter(status="A")

    return j2shim.r2r('webview/group_list.html', \
        {'object_list' : groups, 'letter' : letter, 'al': alphalist}, \
        request=request)
    
def list_labels(request, letter):
    """
    List labels that start with a certain letter.
    """
    if not letter in alphalist or letter == '-':
        letter = '#'
    labels = Label.objects.filter(startswith=letter).filter(status="A")

    return j2shim.r2r('webview/label_list.html', \
        {'object_list' : labels, 'letter' : letter, 'al': alphalist}, \
        request=request)

def list_compilations(request, letter):
    """
    List compilations that start with a certain letter.
    """
    if not letter in alphalist or letter == '-':
        letter = '#'
    compilations = Compilation.objects.filter(startswith=letter)

    return j2shim.r2r('webview/compilation_list.html', \
        {'object_list' : compilations, 'letter' : letter, 'al': alphalist}, \
        request=request)

@login_required
def log_out(request):
    """
    Show a user a form, and then logs user out if a form is sent in to that address.
    """
    if request.method == 'POST':
        logout(request)
        return HttpResponseRedirect("/")
    return j2shim.r2r('webview/logout.html', {}, request=request)

def list_songs(request, letter):
    """
    List songs that start with a certain letter.
    """
    if not letter in alphalist or letter == '-':
        letter = '#'
    songs = Song.objects.select_related(depth=1).filter(startswith=letter)
    return j2shim.r2r('webview/song_list.html', \
        {'object_list' : songs, 'letter' : letter, 'al' : alphalist}, \
        request)

def list_song_history(request, song_id):
    """
    List the queue history belonging to a song
    """
    song = get_object_or_404(Song, id=song_id)
    history = song.queue_set.all()
    return j2shim.r2r('webview/song_history.html', \
        { 'requests' : history, 'song' : song },\
        request=request)

def list_song_votes(request, song_id):
    """
    List the votes belonging to a song
    """
    song = get_object_or_404(Song, id=song_id)
    votes = song.songvote_set.all()
    return j2shim.r2r('webview/song_votes.html', \
        { 'votelist' : votes, 'song' : song },\
        request=request)

def list_song_comments(request, song_id):
    """
    List the comments belonging to a song
    """
    song = get_object_or_404(Song, id=song_id)
    comments = song.songcomment_set.all()
    return j2shim.r2r('webview/song_comments.html', \
        { 'commentlist' : comments, 'song' : song },\
        request=request)

def view_compilation(request, comp_id):
    """
    Try to view a compilation entry.
    """
    comp = get_object_or_404(Compilation, id=comp_id) # Find it, or return a 404 error
    return j2shim.r2r('webview/compilation.html', { 'comp' : comp, 'user' : request.user }, request=request)

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


    
@login_required
def upload_song(request, artist_id):
    artist = get_object_or_404(Artist, id=artist_id)
    auto_approve = getattr(settings, 'ADMIN_AUTO_APPROVE_UPLOADS', 0)
    artist_auto_approve = getattr(settings, 'ARTIST_AUTO_APPROVE_UPLOADS', 1)
    
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
        if form.is_valid():
            new_song = form.save(commit=False)
            new_song.save()
            new_song.artists.add(artist)
            form.save_m2m()
            
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
    return j2shim.r2r('webview/upload.html', \
        {'form' : form, 'artist' : artist }, \
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
            PrivateMessage.objects.create(sender = request.user, to = song.uploader,\
             message = mail_tpl.render(c), subject = "Song Upload Status Changed To: %s" % stat)
    songs = Song.objects.filter(status = "U").order_by('added')
    return j2shim.r2r('webview/uploaded_songs.html', {'songs' : songs}, request=request)

@cache_page(60*15)
def song_statistics(request, stattype):
    songs = None
    title = "Mu"
    stat = None
    numsongs = 100
    if stattype == "voted":
        title = "highest voted"
        #stat = "rating"
        songs = Song.objects.filter(rating_votes__gt = 9).order_by('-rating')[:numsongs]
    if stattype == "favorited":
        title = "most favorited"
        stat = "num_favorited"
        songs = Song.objects.order_by('-num_favorited')[:numsongs]
    if stattype == "queued":
        title = "most played"
        stat = "times_played"
        songs = Song.objects.order_by('-times_played')[:numsongs]
    return j2shim.r2r('webview/stat_songs.html',
                      {'songs': songs, 'title': title, 'numsongs': numsongs, 'stat': stat},
                      request)    

def tag_cloud(request):
    tags = cache.get("tagcloud")
    if not tags:
        min_count = getattr(settings, 'TAG_CLOUD_MIN_COUNT', 1)
        tags = Song.tags.cloud(min_count=min_count)
        cache.set("tagcloud", tags, 15*60)
    c = {'tags': tags}
    return j2shim.r2r('webview/tag_cloud.html', c, request)

def tag_detail(request, tag):
    songs = TaggedItem.objects.get_by_model(Song, tag)
    related = Song.tags.related(tag, counts=True)
    related = tagging.utils.calculate_cloud(related)
    c = {'songs': songs, 'related': related, 'tag':tag}
    return j2shim.r2r('webview/tag_detail.html', c, request)

@login_required
def tag_edit(request, song_id):
    song = get_object_or_404(Song, pk = song_id)
    if request.method == "POST":
        t = request.POST['tags']
        song.tags = re.sub(r'[^a-zA-Z0-9!_\-?& ]+', '', t)
        song.save() # For updating the "last changed" value
        TagHistory.objects.create(user=request.user, song=song, tags = request.POST['tags'])
        return HttpResponseRedirect(song.get_absolute_url())
    tags = tagging.utils.edit_string_for_tags(song.tags)
    changes = TagHistory.objects.filter(song=song).order_by('-id')[:5]
    c = {'tags': tags, 'song': song, 'changes': changes}
    return j2shim.r2r('webview/tag_edit.html', c, request)
    
@login_required
def create_artist(request):
    """
    Simple form to allow registereed users to create a new artist entry.
    """
    auto_approve = getattr(settings, 'ADMIN_AUTO_APPROVE_ARTIST', 0)
    
    if request.method == 'POST':
        # Check to see if moderation settings allow for the check
        if request.user.is_staff and auto_approve == 1:
            # Automatically approved due to Moderator status
            status = 'A'
        else:
            status = 'U'
            
        a = Artist(created_by = request.user, status = status)
        form = CreateArtistForm(request.POST, request.FILES, instance = a)
        if form.is_valid():
            new_artist = form.save(commit=False)
            new_artist.save()
            form.save_m2m()
            return HttpResponseRedirect(new_artist.get_absolute_url())
    else:
        form = CreateArtistForm()
    return j2shim.r2r('webview/create_artist.html', \
        {'form' : form }, \
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
            PrivateMessage.objects.create(sender = request.user, to = artist.created_by,\
             message = mail_tpl.render(c), subject = "Artist Request Status Changed To: %s" % stat)

    artists = Artist.objects.filter(status = "U").order_by('last_updated')
    return j2shim.r2r('webview/pending_artists.html', { 'artists': artists }, request=request)

@login_required
def create_group(request):
    """
    Simple form to allow registereed users to create a new group entry.
    """
    auto_approve = getattr(settings, 'ADMIN_AUTO_APPROVE_GROUP', 0)
    
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
        if form.is_valid():
            new_group = form.save(commit=False)
            new_group.save()
            form.save_m2m()
            return HttpResponseRedirect(new_group.get_absolute_url())
    else:
        form = CreateGroupForm()
    return j2shim.r2r('webview/create_group.html', \
        {'form' : form }, \
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
            PrivateMessage.objects.create(sender = request.user, to = group.created_by,\
             message = mail_tpl.render(c), subject = "Group Request Status Changed To: %s" % stat)

    groups =Group.objects.filter(status = "U").order_by('last_updated')
    return j2shim.r2r('webview/pending_groups.html', { 'groups': groups }, request=request)

@login_required
def create_label(request):
    """
    Simple form to allow registereed users to create a new label entry.
    """
    auto_approve = getattr(settings, 'ADMIN_AUTO_APPROVE_LABEL', 0)
    
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
        if form.is_valid():
            new_label = form.save(commit=False)
            new_label.save()
            form.save_m2m()
            return HttpResponseRedirect(new_label.get_absolute_url())
    else:
        form = CreateLabelForm()
    return j2shim.r2r('webview/create_label.html', \
        {'form' : form }, \
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
            PrivateMessage.objects.create(sender = request.user, to = this_label.created_by,\
             message = mail_tpl.render(c), subject = "Label Request Status Changed To: %s" % stat)

    labels = Label.objects.filter(status = "U").order_by('last_updated')
    return j2shim.r2r('webview/pending_labels.html', { 'labels': labels }, request=request)

@cache_page(60*5)
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
        add_event(event="nowplaying")

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
    
    # Query for each set; Easier to work with templates this way
    link_data_txt = Link.objects.filter(status="A").filter(link_type="T").filter(url_cat=link_cat) # See what linkage data we have
    #link_data_ban = Link.objects.filter(status="A").filter(link_type="B").filter(url_cat=link_cat)
    #link_data_but = Link.objects.filter(status="A").filter(link_type="U").filter(url_cat=link_cat)
    
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

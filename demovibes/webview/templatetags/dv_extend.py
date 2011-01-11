import re, textwrap
from django.core.paginator import Paginator
from django import template
from demovibes.webview.models import *
from demovibes.webview import common
from django.core.cache import cache
from django.conf import settings
from django.contrib.sites.models import Site
from django.template import Context, Template
from django.template.loader import get_template
from forum.models import Forum, Thread, Post, Subscription
import os.path, random
import logging
import j2shim as js
from jinja2 import contextfunction

register = template.Library()

class BetterPaginator(Paginator):
    """
    An enhanced version of the QuerySetPaginator.

    >>> my_objects = BetterPaginator(queryset, 25)
    >>> page = 1
    >>> context = {
    >>>     'my_objects': my_objects.get_context(page),
    >>> }
    """

    def page_range(self, total, current, numshown=10, f=4):
        """
        Return crunched list of pages

        Keywords:
        total -- Total number of pages
        current -- Current page
        numshown -- Approximate size of list (plus close-to-current pages)
                    Max size = numshown + 2 + (f*2)
        f -- Number of close pages to list on each side of current page (default 2)
        """
        if not total or not current:
            return []
        step = total / numshown
        if not step:
            step = 1
        c = 1
        a = []
        while c < total:
            a.append(c)
            c += step
        a.append(total)
        b = current - f
        while b < (current + f + 1):
            if 0 < b < total:
                a.append(b)
            b +=1
        a = list(set(a))
        a.sort()
        return a

    def old_pagerange(self, num_pages, page, range_gap=5):
        """
        Return current page +/- range_gap pages
        """
        if page > 5:
            start = page-range_gap
        else:
            start = 1

        if page < num_pages-range_gap:
            end = page+range_gap+1
        else:
            end = num_pages+1
        return range(start, end)

    def get_context(self, page, range_gap=3):
        try:
            page = int(page)
        except (ValueError, TypeError), exc:
            raise InvalidPage, exc

        paginator = self.page(page)

        pagerange = self.page_range(self.num_pages, page)

        context = {
            'page_range': pagerange,
            'objects': paginator.object_list,
            'num_pages': self.num_pages,
            'page': page,
            'has_pages': self.num_pages > 1,
            'has_previous': paginator.has_previous(),
            'has_next': paginator.has_next(),
            'previous_page': paginator.previous_page_number(),
            'next_page': paginator.next_page_number(),
            'is_first': page == 1,
            'is_last': page == self.num_pages,
        }

        return context

@contextfunction
def paginate(context, obj, limit=None, maxpages=None):
    """
    Paginate object, return (paginated_objectlist, paging_html_code)

    Paginates given object, using the BetterPaginator class.
    It fetches current page via "p" GET variable.
    Returns a paginated object list for given page, and rendered
    HTML code for pages list. It also make sure to preserve GET variables,
    and makes sure there's no multiple "q" variables in GET dict.
    """
    if not limit:
        limit = settings.PAGINATE

    if maxpages:
        totlimit = limit * maxpages
        obj = obj[:totlimit]

    pager = BetterPaginator(obj, limit)
    query_dict = context['request'].GET.copy()

    if 'p' in query_dict:
        del query_dict['p']

    try:
        pag = pager.get_context(context['request'].GET.get('p', 1), 10)
    except:
        return ([], "") # FIXME should raise 404 here, actually

    cntxt = {
        'query_string': query_dict.urlencode(),
        'paginator': pag,
    }

    paging = js.r2s('webview/t/paginate.html', cntxt)
    return (cntxt['paginator']['objects'], paging)

@register.simple_tag
def site_name():
    current_site = Site.objects.get_current()
    return current_site.name

@register.simple_tag
def site_url():
    current_site = Site.objects.get_current()
    return current_site.domain

@register.simple_tag
def get_online_users():
    result = cache.get("online_users")
    # This is designed specifically for Sidebar use. Its mostly a copy
    # Of Terrasque's original code
    if not result:
        timefrom = datetime.datetime.now() - datetime.timedelta(minutes=5)
        userlist = Userprofile.objects.filter(last_activity__gt=timefrom).order_by('user__username')

        # Stuff this into an object
        result = js.r2s('webview/whos_online_sb.html', { 'userlist' : userlist })
        cache.set("online_users", result, 60)
    return result

@register.tag
def get_rating_stars_song_avg(parser, token):
    """
    Attempt to get a rating for the song, in formatted stars. Value is based
    From average vote value, and code will ater star shapes. Makes use of the
    GetSongRatingStarsAvgNode() class.
    """
    try:
        tag_name, username = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires exactly one argument" % token.contents.split()[0]

    # Send this out for processing. Don't come back without pizza! hehe
    return GetSongRatingStarsAvgNode(username)

@register.tag
def get_text_links(parser, token):
    """
    Can be called from any template. Will insert all text links for the specified category
    ID number into the current page. Tried to make as much of this a template as possible.
    This will also insert a header object for the category, if links exist.
    """
    try:
        tag_name, slugname = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires exactly one argument" % token.contents.split()[0]
    return GetTextLinkEntries(slugname)

@register.tag
def count_text_links(parser, token):
    """
    Counts the number of links in the specified link category slug
    """
    try:
        tag_name, slugname = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires exactly one argument" % token.contents.split()[0]
    return CountTextLinkEntries(slugname)

def get_banner_links(parser, token):
    """
    """
    return

def pending(category):
    c = {
        'songs': Song.objects.filter(status="U"),
        'artists': Artist.objects.filter(status="U"),
        'groups': Group.objects.filter(status="U"),
        'labels': Label.objects.filter(status="U"),
        'links': Link.objects.filter(status="P"),
        'info': SongMetaData.objects.filter(checked=False),
    }
    r = cache.get("pend_"+category)
    if not r:
        if category in c.keys():
            r = c[category].count()
        cache.set("pend_"+category, r, 60)
    return r and "(%d)" % r or ""

def get_button_links(parser, token):
    """
    """
    return

@register.simple_tag
def logo():
    """
    Returns a random logo
    """
    randlogo = cache.get("current_logo")
    if not randlogo:
        try:
            numLogos = Logo.objects.filter(active=True).count()
            rand = random.randint(0, numLogos - 1)
            L = Logo.objects.filter(active=True)[rand]
            logo = L.file.url
            alt = "#%s - By %s" % (L.id, L.creator)
        except:
            logo = "%slogos/default.png" % settings.MEDIA_URL
            alt = "Logo"
        randlogo = '<img id="logo" src="%s" title="%s" alt="%s" />' % (logo, alt, alt)
        cache.set("current_logo", randlogo, 60*15)
    return randlogo

def current_song(user = None):
    """
    Returns the current song playing. Ties into right-panel on all views.
    """
    now = common.get_now_playing()
    if user:
        Q = common.get_now_playing_song()
        if not Q:
            return ""
        if user.is_authenticated():
            vote = Q.song.get_vote(user) or 0
        else:
            vote = 0
        c = {
            'song': Q.song,
            'now_playing': Q,
            'myvote': vote,
            'voterange': [1, 2, 3, 4, 5],
            'user': user,
        }
        voteinfo = js.r2s("webview/t/now_playing_vote.html", c)
        if Q.song.get_metadata().ytvidid and (not user or not user.is_authenticated() or user.get_profile().show_youtube):
            ytinfo = js.r2s("webview/t/now_playing_youtube.html", c)
        else:
            ytinfo = ""
        now = now + ytinfo + voteinfo
    return now

@register.simple_tag
def ajaxevent():
    """
    Returns the latest ajax event in the table, or 0 if there are none.
    """
    return common.get_latest_event()

@register.simple_tag
def get_oneliner():
    """
    Renders the oneliner html
    """
    oneliner = common.get_oneliner()
    R = js.r2s('webview/oneliner2.html', {'oneliner' : oneliner})
    return R

@register.tag
def get_post_count(parser, token):
    """
    Simple tag to return the forum post count of any specified user. In the event it craps out, 0 is returned. This
    Most likely could be optimized in the future.
    """
    try:
        tag, user = token.split_contents()
    except:
        raise template.TemplateSyntaxError, "%r tag requires one argument" % token.contents.split()[0]
    return GetPostCount(user)

def user_css(user):
    try:
        return user.get_profile().get_css()
    except:
        return getattr(settings, 'DEFAULT_CSS', "%sthemes/default/style.css" % settings.MEDIA_URL)

@register.tag
def css(parser, token):
    """
    Returns CSS path
    """
    try:
        tag, user = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires one argument" % token.contents.split()[0]
    return GetCss(user)

@register.tag
def get_inbox(parser, token):
    """
    Returns inbox unread messages
    """
    try:
        tag, user = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires one argument" % token.contents.split()[0]
    return GetInboxNode(user)

@register.tag
def get_vote(parser, token):
    """
    Sets variable "vote_value" to the user's vote.
    """
    try:
        tag_name, song_object, user = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires three arguments" % token.contents.split()[0]
    return GetVoteNode(song_object, user)

@register.tag
def get_song_rating(parser, token):
    """
    Sets variable "song_rating" to the rating of the song specified on parameters
    """
    try:
        tag_name, song_object = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires two arguments" % token.contents.split()[0]
    return GetSongRatingNode(song_object)

@register.tag
def get_song_queuetag(parser, token):
    """
    Aut-add any song number to a template with queueing capabilities. Specify the song number
    After the command. Example: {% get_song_queuetag 5 %} # Adds a full link and queue click for song #5
    This version is designed specifically for template use only.
    """
    try:
        tag_name, song = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires two arguments" % token.contents.split()[0]
    return GetSongQueueTag(song)

def get_news(status="B"):
    return News.objects.filter(status = status)

@register.tag
def get_sidebar_news(parser, token):
    news = News.objects.filter(status = 'B')
    return SidebarNewsNode(news)

@register.tag
def get_streams(parser, token):
    streams = RadioStream.objects.filter(active = True)
    return StreamListNode(streams)

@register.tag
def is_favorite(parser, token):
    """
    Sets variable "is_favorite" to true or false.
    """
    try:
        tag_name, song_object, user = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires two arguments" % token.contents.split()[0]
    return IsFavoriteNode(song_object, user)

class GetSongRatingNode(template.Node):
    def __init__(self, song):
        self.song = song

    def render(self, context):
        try:
            song = template.resolve_variable(self.song, context)
            context['song_rating'] = song.rating
        except:
            pass
        return ''

class GetSongRatingStarsAvgNode(template.Node):
    """
    Python implementation of star system, computes the star code directly in Python and
    Returns the result as a string of HTML that can be inserted into the user template. Should
    Be fully compatible with BombmanDK's ajax functions. This fixes the issues with HTML being
    Cached all the time. AAK.

    This function is in bad need of some templating. AAK.
    """
    def __init__(self, username):
        self.username = username

    def render(self, context):
        try:
            songtype = Queue.objects.select_related(depth=2).filter(played=True).order_by('-time_played')[0]
            song = songtype.song
        except:
            # Exception is thrown if no song data from queue exists. Simply return 'No Song'
            return "No Song!"

        # Now we have passed the exception issue with the song, we can access ther rest
        # Of the data needed for this request.
        try:
            user = template.resolve_variable(self.username, context)
            song_rating = song.rating
            vote_count = song.rating_votes
        except:
            # This in case something fails terribly!!
            song_rating = 0
            vote_count = 0

        # Make sure song.rating is a real variable and has a value, otherwise default it to 0
        if(type(song.rating).__name__=='NoneType'):
            song_rating = 0
            vote_count = 0

        # Detect if this user is anonymous
        try:
                if(type(user).__name__=='AnonymousUser'):
                    # Anonymous users never have a vote, and can be identified later without DB call
                    user_vote = 0
                    user_anon = True
                else:
                    user_vote = song.get_vote(user) # What did the user vote for this song?
                    user_anon = False
        except:
            user_vote = 0
            user_anon = True

        htmltxt = ""
        TempLine = ""

        # This fixes an issue where UserVote doesnt actually exist yet. I have generated this
        # Error several times on the dev server. This fixes the problem.
        try:
            if(type(user_vote).__name__=='str'):
                user_vote = int(0) # Implicitly define this as int, so there is no confusion!
        except:
            user_vote = int(0); # Throws an exception in some odd situations

        htmltxt = common.get_now_playing()

        # Open the table
        htmltxt = htmltxt + '<table class="vote" name="vote-%d" onmouseout="voteshow(\'vote-%d\', %d);">\n' % ( song.id, song.id, user_vote )
        htmltxt = htmltxt + '<tr>\n'

        for count in range(1, 6):
            DiffVal = (count - user_vote) # Pre-calc rating difference
            TempLine = '<td align="center" onmouseover="voteshow(\'vote-%d\', %d);" onmouseout="voteshow(\'vote-%d\', %d);">' % (song.id, count, song.id, user_vote)

            if(user_anon == False):
                TempLine = TempLine + '<a href="/demovibes/song/%d/vote/%d/">' % ( song.id, count )

            if(count > user_vote):
                # Represent stars AFTER the current rated star
                TempLine = TempLine + '<img src="/static/star-white.png" title="%d Star" border="0" id="vote-%d-%d" />' % ( count, song.id, count )
            else:
                # This represents a star already under/up to the rating
                TempLine = TempLine + '<img src="/static/star-red.png" title="%d Star" border="0" id="vote-%d-%d" />' % ( count, song.id, count )

            if(user_anon == False):
                TempLine = TempLine + '</a>'

            TempLine = TempLine + "</td>\n" # Close the column

            # Add this to the final text string
            htmltxt = htmltxt + TempLine

        # Spacer
        htmltxt = htmltxt + '<td> </td>'

        # Go ahead and determine if this is a fave or not
        if(user_anon == False):
            T = loader.get_template('webview/t/fav_icon.html')
            C = Context({'song' : song, 'user' : user})
            FavIconTxt = T.render(C)
            htmltxt = htmltxt + '<td>%s</td>' % (FavIconTxt)

        # Add a link to voting history
        htmltxt = htmltxt + '<td><a href="/demovibes/song/%d/votes/"><img class="song_head" src="/static/script.png" title="Voting History" /></a></td>' % (song.id)

        # Close off the rest of the table/span
        htmltxt = htmltxt + '</tr>\n'
        htmltxt = htmltxt + '</table>\n'

        # Insert the rating/Vote counts info
        if(user_anon == False):
            htmltxt = htmltxt + 'Your Vote: %d<br />' % (user_vote)

        htmltxt = htmltxt + 'Rating: %.2f (%d Votes)<br />' % (song_rating, vote_count )

        # Return the newly computed images html string
        return htmltxt


def get_text_link_entries(slug):
        try:
            # Look for the identifiying slug
            slug_id = LinkCategory.objects.get(id_slug = slug)
        except:
            # No matching slug was found!
            return None

        # We have a slug; Now to see if it has any links
        try:
            site_links = Link.objects.filter(status="A").filter(link_type="T").filter(url_cat=slug_id).order_by('-priority')

            # Filter out categories which have no links in them!
            if len(site_links) == 0:
                return " " # Prevents 'None' from being displayed

            # We got the goods, let's go with it!
            T = loader.get_template('webview/t/link_category_header.html')
            C = Context({ 'LC' : slug_id })
            header = T.render(C)

            T = loader.get_template('webview/links_text_all.html')
            C = Context({ 'text_links' : site_links })
            return header + T.render(C)
        except:
            # Something borked!
            return None

"""
Simple tag to suck all text link entries out of the system for the specified
Category slug. Should work in any template.
"""
class GetTextLinkEntries(template.Node):
    def __init__(self, slugname):
        self.slugname = slugname

    def render(self, context):
        try:
            # Look for the identifiying slug
            slug = template.resolve_variable(self.slugname, context)
            slug_id = LinkCategory.objects.get(id_slug = slug)
        except:
            # No matching slug was found!
            return None

        # We have a slug; Now to see if it has any links
        try:
            site_links = Link.objects.filter(status="A").filter(link_type="T").filter(url_cat=slug_id).order_by('-priority')

            # Filter out categories which have no links in them!
            if len(site_links) == 0:
                return " " # Prevents 'None' from being displayed

            # We got the goods, let's go with it!
            T = loader.get_template('webview/t/link_category_header.html')
            C = Context({ 'LC' : slug_id })
            header = T.render(C)

            T = loader.get_template('webview/links_text_all.html')
            C = Context({ 'text_links' : site_links })
            return header + T.render(C)
        except:
            # Something borked!
            return None

"""
Count the number of links in the specified category slug.
"""
class CountTextLinkEntries(template.Node):
    def __init__(self, slugname):
        self.slugname = slugname

    def render(self, context):
        try:
            # Look for the identifiying slug
            slug = template.resolve_variable(self.slugname, context)
            slug_id = LinkCategory.objects.get(id_slug = slug)
        except:
            # No matching slug was found!
            return 0

        # We have a slug; Now to see if it has any links
        try:
            site_links = Link.objects.filter(status="A").filter(link_type="T").filter(url_cat=slug_id).order_by('-priority')
        except:
            # No links, or something borked!
            return 0

        # We got the goods, let's go with it!
            return len(site_links)

class GetCss(template.Node):
    def __init__(self, user):
        self.user = user

    def render(self, context):
        try:
            user = template.resolve_variable(self.user, context)
            return user.get_profile().get_css()
        except:
            return getattr(settings, 'DEFAULT_CSS', "%sthemes/default/style.css" % settings.MEDIA_URL)

def j_get_post_count(user):
    return Post.objects.filter(author=user).count()

class GetPostCount(template.Node):
    """
    Returns the numeric post count for the user in the passed arguments.
    """
    def __init__(self, user):
        self.user = user

    def render(self, context):
        try:
            user = template.resolve_variable(self.user, context)
            obj =Post.objects.filter(author=user)
            return len(obj)
        except:
            return 0

def get_unread_count(user):
    nr = PrivateMessage.objects.filter(to=user, unread=True, visible = True).count()
    if not nr:
        return ""
    return "(%s)" % nr

class GetInboxNode(template.Node):
    def __init__(self, user):
        self.user = user

    def render(self, context):
        try:
            user = template.resolve_variable(self.user, context)
            nr = PrivateMessage.objects.filter(to=user, unread=True, visible = True)
            nr = nr.count()
            if nr > 0:
                return "(%s)" % nr
            return ''
        except:
            return 'Err'


class SidebarNewsNode(template.Node):
    def __init__(self, news):
        self.news = news

    def render(self, context):
        context['sidebarnews'] = self.news
        return ""

class StreamListNode(template.Node):
    def __init__(self, streams):
        self.streams = streams

    def render(self, context):
        context['radiostreams'] = self.streams
        return ""

class GetVoteNode(template.Node):
    def __init__(self, song, user):
        self.song = song
        self.user = user

    def render(self, context):
        try:
            user = template.resolve_variable(self.user, context)
            song = template.resolve_variable(self.song, context)
            context['vote_value'] = song.get_vote(user)
        except:
            pass
        return ''

class IsFavoriteNode(template.Node):
    def __init__(self, song, user):
        self.song = song
        self.user = user

    def render(self, context):
        try:
            user = template.resolve_variable(self.user, context)
            song = template.resolve_variable(self.song, context)
            context['is_favorite'] = song.is_favorite(user)
        except:
            pass
        return ''

def get_song_queue_tag_j(origsong):
    #origsong = Song.objects.get(id = song.remix_of_id)
    artists = origsong.get_metadata().artists
    return js.r2s('webview/queue_tag.html', { 'song' : origsong, 'artists' : artists })

def get_song_queue_tag(song_id):
    try:
        song_obj = Song.objects.get(id = song_id)
        artists = song_obj.get_metadata().artists

        T = loader.get_template('webview/queue_tag.html')
        C = Context({ 'song' : song_obj, 'artists' : artists })
        return T.render(C)
    except:
        return unicode(song_id)

class GetSongQueueTag(template.Node):
    def __init__(self, song):
        self.song = song

    def render(self, context):
        try:
            song = template.resolve_variable(self.song, context)
            song_obj = Song.objects.get(id = song)
            artists = song_obj.get_metadata().artists

            T = loader.get_template('webview/queue_tag.html')
            C = Context({ 'song' : song_obj, 'artists' : artists })
            return T.render(C)

        except:
            pass
        return 'Invalid Song_ID'

def bb_artist(hit):
    """
    Insert an artist into BBCode by their ID, using our template
    """
    try:
        artistid = hit.group(1)
        artist = Artist.objects.get(id=artistid)
        T = loader.get_template('webview/t/artist.html')
        C = Context({'A' : artist})
        return T.render(C)
    except:
        return "[artist]%s[/artist]" % artistid

def bb_queue(hit):
    """
    Attempt to insert a song with queue information. The Song number is specified in the
    Tag, the output is the name of the song, followed by the authors and a green + if the
    Song is unlocked, or a padlock if locked. The + can be clicked by the user and added to
    Queue. This will work for users who are not logged in, however it will throw them to the
    Login screen if they try to request while not logged in. AAK.
    """
    try:
        songid = hit.group(1)
        song = Song.objects.get(id=songid)
        artists = song.get_metadata().artists
    except:
        return "[queue]%s[/queue]" % songid

    t = loader.get_template('webview/queue_tag.html')
    c = Context({
        'song' : song,
        'artists' : artists,
        'MEDIA_URL' : settings.MEDIA_URL,
        })

    result = t.render(c)
    return result

def bb_song(hit):
    """
    Insert a link directly to a song by it's ID number.
    """
    try:
        songid = hit.group(1)
        song = Song.objects.get(id=songid)
    except:
        return "[song]%s[/song]" % songid

    # Use the existing Songname template already present in code
    t = loader.get_template('webview/t/songname.html')
    c = Context({
        'song' : song,
    })

    return t.render(c)

def bb_flag(hit):
    """
    Allow forum post to return a flag code. Uses standard 2-digit flag code
    Such as us, gb, sc etc. If an invalid flag is specified, or null, the default
    Nectaflag is used. Flag created for me by sark76 (Mark Huther). AAK
    """
    flagcode = hit.group(1)
    flag = flagcode.lower().encode('ascii', 'ignore')

    if os.path.isfile(os.path.join(settings.DOCUMENT_ROOT, "flags", "%s.png" % flag)):
        return "<img src='%sflags/%s.png' class='countryflag' alt='flag' title='%s' />" % (settings.MEDIA_URL, flag, flag)

    # No flag image found, so default to Necta flag
    return "<img src='%sflags/nectaflag.png' class='countryflag' title='flag' />" % (settings.MEDIA_URL)

def bb_user(hit):
    """
    Insert the name of a user, and add a little bloke next to it to signify
    That they are a user. No extensive validation is done here. Eventually, we should add
    User verification.
    """
    try:
        user = hit.group(1)
        U = User.objects.get(username=user)
        T = loader.get_template('webview/t/user.html')
        C = Context({'U' : U})
        return T.render(C)

    except:
        # This is normally thrown when the user is invalid. Return the original result,
        # Only we add an icon to indicate an invalid user.
        return '<img src="/static/user_error.png" alt="user" border="0" />%s' % (user)

def bb_artistname(hit):
    """
    Insert an artist into the BBCode by name, using our template
    """
    try:
        artist = hit.group(1)
        A = Artist.objects.get(handle=artist)
        T = loader.get_template('webview/t/artist.html')
        C = Context({'A' : A})
        return T.render(C)
    except:
        # This is normally thrown when the artist is invalid. Return the original result,
        # Only we add an icon to indicate an invalid artist.
        return '<img src="/static/user_error.png" alt="artist" border="0" /> %s' % (artist)

def bb_group(hit):
    """
    Insert a group into BBCode by it's ID number, using our template
    """
    try:
        groupid = hit.group(1)
        group = Group.objects.get(id=groupid)
        T = loader.get_template('webview/t/group.html')
        C = Context({'G' : group})
        return T.render(C)
    except:
        return "[group]%s[/group]" % groupid

def bb_groupname(hit):
    """
    Insert a group into BBCode by it's name, using our group template.
    """
    try:
        group = hit.group(1)
        G = Group.objects.get(name=group)
        T = loader.get_template('webview/t/group.html')
        C = Context({'G' : G})
        return T.render(C)
    except:
        # This is normally thrown when the group is invalid. Return the original result,
        # Only we add an icon to indicate an invalid group.
        return '<img src="/static/user_error.png" alt="user" border="0" /> %s' % (group)

def bb_label(hit):
    """
    Insert a production label by it's ID number
    """
    try:
        labelid = hit.group(1)
        label = Label.objects.get(id=labelid)
        T = loader.get_template('webview/t/label.html')
        C = Context({ 'L' : label })
        return T.render(C)
    except:
        # Usually thrown if the ID is invalid or doesn't exist
        return '[label]%s[/label]' % (labelid)

def bb_labelname(hit):
    """
    Identify a production label by it's real name, using the template system.
    """
    try:
        real_name = hit.group(1)
        L = Label.objects.get(name=real_name)
        T = loader.get_template('webview/t/label.html')
        C = Context({ 'L' : L })
        return T.render(C)
    except:
        # This will throw if the requested label is spelt incorrectly, or doesnt exist
        return '<img src="/static/transmit.png" alt="Invalid Label" border="0" /> %s' % (real_name)

def bb_platform(hit):
    """
    Insert a platform by it's ID number
    """
    try:
        plat_id = hit.group(1)
        platform = SongPlatform.objects.get(id=plat_id)
        T = loader.get_template('webview/t/platformname.html')
        C = Context({ 'P' : platform })
        return T.render(C)
    except:
        # Usually thrown if the ID is invalid or doesn't exist
        return '[platform]%s[/platform]' % (plat_id)

def bb_platformname(hit):
    """
    Identify a platform by it's real name
    """
    try:
        plat_name = hit.group(1)
        P = SongPlatform.objects.get(title=plat_name)
        T = loader.get_template('webview/t/platformname.html')
        C = Context({ 'P' : P })
        return T.render(C)
    except:
        # This will throw if the requested platform is spelt incorrectly, or doesnt exist
        return '[platform]%s[/platform]' % (plat_name)

def bb_thread(hit):
    """
    Attempt to find a forum post made with the selected ID number, and insert
    Its title along with a clickable link & icon.
    """
    try:
        post_id = hit.group(1)
        t = Thread.objects.get(id=post_id)
        return '<a href="%s"><img src="%snewspaper.png" alt="forum" border="0" /> %s</a>' % (t.get_absolute_url(), settings.MEDIA_URL, t)
    except:
        return "[thread]%s[/thread]" % (post_id)

def bb_forum(hit):
    """
    Add a forum link by it's slug. Link is made clickable.
    """
    try:
        forum_slug = hit.group(1)
        f = Forum.objects.get(slug=forum_slug)
        return '<a href="%s"><img src="%snewspaper.png" alt="forum" border="0" /> %s</a>' % (f.get_absolute_url(), settings.MEDIA_URL, f)
    except:
        return "[forum]%s[/forum]" % (forum_slug)

def bb_size(hit):
    """
    Insert a text entry at a specified pixel size. Quite clever in that it will look for a
    Min/Max font height and auto adapt accordingly. Stops the text becoming too small or
    Too large! AAK: Move size settings to settings.py
    """

    size = hit.group(1)
    text = hit.group(2)

    minimum = getattr(settings, 'BBCODE_MINIMUM', 6)
    maximum = getattr(settings, 'BBCODE_MAXIMUM', 50)

    # Size needs to be controlled, and may vary depending on the CSS on the site. We don't want
    # Users requesting a size too small to be visible, or too large and take up the whole screen!
    # This could eventually go into the settings.py file, hehe.
    if(int(size) < minimum):
        return '<font style="font-size: %dpx">%s [Too Small, Upscaled To 6]</font>' % (minimum, text)

    if(int(size) > maximum):
        return '<font style="font-size: %dpx">%s [Too Large, Reduced To 50]</font>' % (maximum, text)

    # Return the normal text size
    return '<font style="font-size: %dpx">%s</font>' % (int(size), text)

def bb_youtube(hit):
    """
    Simplified YouTube video sharing tab. Embed the ID of the video into the [youtube]
    Tag like so: [youtube]S-T8h0T0SK8[/youtube]
    """
    video = hit.group(1)
    return '<object width="425" height="350"><param name="movie" value="http://www.youtube.com/v/%s"></param><param name="wmode" value="transparent"></param><embed src="http://www.youtube.com/v/%s" type="application/x-shockwave-flash" wmode="transparent" width="425" height="350"></embed></object>' % (video, video)

def bb_compilation(hit):
    """
    Attempt to find a compilation by it's ID number
    """
    comp = hit.group(1)
    try:
        C = Compilation.objects.get(id=comp)
        T = loader.get_template('webview/t/compilation.html')
        Co = Context({'C' : C})
        return T.render(Co)
    except:
        return '[album]%s[/album]' % (comp)

def bb_compilation_name(hit):
    """
    Attempt to find a compilation entry by it's name.
    """
    comp = hit.group(1)
    try:
        C = Compilation.objects.get(name=comp)
        T = loader.get_template('webview/t/compilation.html')
        Co = Context({'C' : C})
        return T.render(Co)
    except:
        return '[album]%s[/album]' % (comp)

def bb_faq(hit):
    """
    Create a clickable FAQ link.
    """
    faqq = hit.group(1)
    try:
        F = Faq.objects.get(id=faqq)
        T = loader.get_template('webview/t/faq_question.html')
        Q = Context({'F' : F})
        return T.render(Q)
    except:
        return '[faq]%s[/faq]' % (faqq)

def bb_youtube_ol(hit):
    """
    Simplified YouTube video sharing tab. Embed the ID of the video into the [yt]
    Tag like so: [yt]S-T8h0T0SK8[/yt]. This version is oneliner specific
    """
    video = hit.group(1)
    return '<a href="http://www.youtube.com/watch?v=%s" target="_new"><img src="/static/youtube_icon.png" title="YouTube" alt="YouTube" border="0" /> YouTube Link</a>' % (video)

def bb_googlevideo_ol(hit):
    """
    """
    video = hit.group(1)
    return '<a href="http://video.google.com/videoplay?docid=%s" target="_new"><img src="/static/googlevideo_icon.png" title="Google Video" alt="Google Video" border="0"> Google Video Link</a>' % (video)

def bb_youtube_name_ol(hit):
    """
    Simplified YouTube video sharing tab. Embed the ID of the video into the [yt]
    Tag like so: [yt=Title]S-T8h0T0SK8[/yt]. This version is oneliner specific and
    Places Title as the clickable value.
    """
    video = hit.group(1)
    title = hit.group(2)

    return '<a href="http://www.youtube.com/watch?v=%s" target="_new"><img src="/static/youtube_icon.png" title="YouTube" alt="YouTube" border="0"> %s</a>' % (title, video)

def bb_gvideo(hit):
    """
    Google Video isn't as advanced as YouTube for clicps and so forth yet, however
    We still add the video in pretty mush the same way: [gvideo]1199004375595376444[/gvideo]
    """
    video = hit.group(1)
    return '<object width="400" height="326"><param name="movie" value="http://video.google.com/googleplayer.swf?docId=%s"></param><param name="wmode" value="transparent"></param><embed src="http://video.google.com/googleplayer.swf?docId=%s" wmode="transparent" style="width:400px; height:326px;" id="VideoPlayback" type="application/x-shockwave-flash" flashvars=""></embed></object>' % ( video, video )

@register.filter
def oneliner_mediaparse(value):
    """
    """
    medialinks = [
        # YouTube auto scraping
        (r'http://www.youtube.com/watch/v=([\w&;=-]+)', r'[yt]\1[/yt]'),
        (r'http://youtube.com/watch?v=([\w&;=-]+)', r'[yt]\1[/yt]'),
        (r'http://www.youtube.com/watch\?v=([\w&;=-]+)', r'[yt]\1[/yt]'),
        (r'http://www.youtube.com/v/([\w&;=-]+)', r'[yt]\1[/yt]'),

        # Google Video Scraping
        (r'http://video.google.com/videoplay\?docid=([\w&;=-]+)', r'[gv]\1[/gv]'),
    ]

    for mset in medialinks:
        p = re.compile(mset[0], re.DOTALL)
        value = p.sub(mset[1], value)

    return value

@register.filter
def bbcode(value):
    """
    Decodes BBcode and replaces it with HTML
    """

    for bbset in bbdata_full:
        p = bbset[0]
        value = p.sub(bbset[1], value)

    #The following two code parts handle the more complex list statements
    temp = ''
    p = re.compile(r'\[list\](.+?)\[/list\]', re.DOTALL)
    m = p.search(value)
    if m:
        items = re.split(re.escape('[*]'), m.group(1))
        for i in items[1:]:
            temp = temp + '<li class="bblist">' + i + '</li>'
        value = p.sub(r'<ul>'+temp+'</ul>', value)

    temp = ''
    p = re.compile(r'\[list=(.)\](.+?)\[/list\]', re.DOTALL)
    m = p.search(value)
    if m:
        items = re.split(re.escape('[*]'), m.group(2))
        for i in items[1:]:
            temp = temp + '<li>' + i + '</li>'
        value = p.sub(r'<ol type="\1">'+temp+'</ol>', value)

    return value

@register.filter
def bbcode_oneliner(value):
    """
    Replace BBCode tags with HTML equivalents. Purposely placed into seperate
    Function for Oneliner purposes, as over time the tags may truncate or change
    or use specifically within the oneliner & it's limitations. AAK.
    """
    for bbset in bbdata_oneliner:
        p = bbset[0]
        nr = p.sub(bbset[1], value)
    return value

@register.filter
def wordwrap(value, arg=80):
    """
    Wrap a text, breaking long words.
    """
    return "\n".join(textwrap.wrap(value, int(arg)))

@register.filter
def smileys_oneliner(value):
    """
    Replaces smiley text with images. First, do secret smileys so we can replace
    Smileys pre-converted with others later.
    """

    num_smileys = 0
    PER_SMILEY = getattr(settings, "ONELINER_PER_SMILEY_LIMIT", 0)
    TOTAL_SMILEY = getattr(settings, "ONELINER_TOTAL_SMILEY_LIMIT", None)
    for bbset in SMILEYS:
        p = bbset[0]
        (value, nr) = p.subn(bbset[1], value, PER_SMILEY)
        num_smileys = num_smileys + nr
        if TOTAL_SMILEY and TOTAL_SMILEY <= num_smileys:
            return value
    return value

@register.filter
def smileys(value):
    """
    Replaces smiley text with images. First, do secret smileys so we can replace
    Smileys pre-converted with others later.
    """

    num_smileys = 0
    PER_SMILEY = getattr(settings, "OTHER_PER_SMILEY_LIMIT", 0)
    TOTAL_SMILEY = getattr(settings, "OTHER_TOTAL_SMILEY_LIMIT", None)
    for bbset in SMILEYS:
        p = bbset[0]
        (value, nr) = p.subn(bbset[1], value, PER_SMILEY)
        num_smileys = num_smileys + nr
        if TOTAL_SMILEY and TOTAL_SMILEYS <= num_smileys:
            return value
    return value

@register.filter
def flag(value):
    """
    Shows a flag instead of 2 letter country code. If the flag is invalid, a nectaflag is
    Used. Flag was created for me by sark76 (Mark Huther). AAK
    """
    flag = value.lower().encode('ascii', 'ignore')
    if os.path.isfile(os.path.join(settings.DOCUMENT_ROOT, "flags", "%s.png" % flag)):
        return "<img src='%sflags/%s.png' class='countryflag' alt='flag' title='%s' />" % (settings.MEDIA_URL, flag, flag)

    # No flag image found, return the Necta flag hehe
    return "<img src='%sflags/nectaflag.png' class='countryflag' alt='flag' />" % (settings.MEDIA_URL)

@register.filter
def getattrs (obj, args):
    """ Try to get an attribute from an object.

    Example: {% if block|getattr:"editable,True" %}

    Beware that the default is always a string, if you want this
    to return False, pass an empty second argument:
    {% if block|getattr:"editable," %}
    """
    splitargs = args.split(',')
    try:
      (attribute, default) = splitargs
    except ValueError:
      (attribute, default) = args, ''

    try:
      attr = obj.__getattribute__(attribute)
    except AttributeError:
      attr = obj.__dict__.get(attribute, default)
    except:
      attr = default

    if hasattr(attr, '__call__'):
        return attr.__call__()
    else:
        return attr

@register.filter
def dv_urlize(text):
    """
    Simplified replacement of the urlize filter in Django, which at present offers no option
    To allow a link to open in a new tab/window. AAK.
    """
    part1 = re.compile(r"(^|[\n ])(((news|telnet|nttp|irc|http|ftp|https)://[\w\#$%&~.\-;:=,?@\[\]+]*)(/[\w\#$%&~/.\-;:=,?@\[\]+]*)?)", re.IGNORECASE | re.DOTALL)
    part2 = re.compile(r"(^|[\n ])(((www|ftp)\.[\w\#$%&~.\-;:=,?@\[\]+]*)(/[\w\#$%&~/.\-;:=,?@\[\]+]*)?)", re.IGNORECASE | re.DOTALL)

    # Make a quick copy of our variable to work with
    link = text

    # Depending on your personal preference, you can choose one of two things with the following
    # Lines of code. If the value of SHORTEN_ONELINER_LINKS is set to 1, links appear in the
    # Oneliner in a truncated format. Any other value inserts the full link. Default: 0

    link_type = getattr(settings, 'SHORTEN_ONELINER_LINKS', 0)

    if(link_type == 1):
        # Truncate displayed links to just the starting address.
        link = part1.sub(r'\1<a href="\2" target="_blank">\3</a>', link)
        link = part2.sub(r'\1<a href="http://\2" target="_blank">\3</a>', link)
    else:
        # Show them as they originally were added.
        link = part1.sub(r'\1<a href="\2" target="_blank">\2</a>', link)
        link = part2.sub(r'\1<a href="http://\2" target="_blank">\2</a>', link)

    # Return the results of the conversion
    return link

bbdata_oneliner = [
        (r'\[url\](.+?)\[/url\]', r'<a href="\1" target="_new">\1</a>'),
        (r'\[url=(.+?)\](.+?)\[/url\]', r'<a href="\1" target="_new">\2</a>'),
        (r'\[email\](.+?)\[/email\]', r'<a href="mailto:\1">\1</a>'),
        (r'\[email=(.+?)\](.+?)\[/email\]', r'<a href="mailto:\1">\2</a>'),

        # img test is a little modified for oneliner. Using a baseheight of 20
        # Pixels, we scale the image proportionally. The outcome of the tag is a
        # Clickable thiumbnail, which opens in a new tab.

        # This can be abused too much right now, commenting out
        #(r'\[img\](.+?)\[/img\]', r'<a href="\1" target="_new"><img src="\1" height="20" alt="" \></a>'),
        #(r'\[img=(.+?)\](.+?)\[/img\]', r'<a href="\1" target="_new"><b>\2</b> <img src="\1" alt="" height="20" \></a>'),

        # Standard text display tags for bold, underline etc.
        (r'\[b\](.+?)\[/b\]', r'<strong>\1</strong>'),
        (r'\[i\](.+?)\[/i\]', r'<i>\1</i>'),
        (r'\[u\](.+?)\[/u\]', r'<u>\1</u>'),
        (r'\[s\](.+?)\[/s\]', r'<s>\1</s>'),

        # Big and Small might be taken out of oneliner, we'll see how they are used.
        (r'\[big\](.+?)\[/big\]', r'<big>\1</big>'),
        (r'\[small\](.+?)\[/small\]', r'<small>\1</small>'),

        # Standard colour tags for use in the oneliner. Most basic colours are pre-made
        # For ease of use. Feel free to add new colours.
        (r'\[red\](.+?)\[/red\]', r'<font color="red">\1</font>'),
        (r'\[green\](.+?)\[/green\]', r'<font color="green">\1</font>'),
        (r'\[blue\](.+?)\[/blue\]', r'<font color="blue">\1</font>'),
        (r'\[brown\](.+?)\[/brown\]', r'<font color="brown">\1</font>'),
        (r'\[cyan\](.+?)\[/cyan\]', r'<font color="cyan">\1</font>'),
        (r'\[darkblue\](.+?)\[/darkblue\]', r'<font color="darkblue">\1</font>'),
        (r'\[gold\](.+?)\[/gold\]', r'<font color="gold">\1</font>'),
        (r'\[grey\](.+?)\[/grey\]', r'<font color="gray">\1</font>'),
        (r'\[magenta\](.+?)\[/magenta\]', r'<font color="magenta">\1</font>'),
        (r'\[orange\](.+?)\[/orange\]', r'<font color="orange">\1</font>'),
        (r'\[pink\](.+?)\[/pink\]', r'<font color="pink">\1</font>'),
        (r'\[purple\](.+?)\[/purple\]', r'<font color="purple">\1</font>'),
        (r'\[white\](.+?)\[/white\]', r'<font color="white">\1</font>'),
        (r'\[yellow\](.+?)\[/yellow\]', r'<font color="yellow">\1</font>'),
        (r'\[black\](.+?)\[/black\]', r'<font color="black">\1</font>'),

        # For those who want a bit extra pazazz, we can specify a HTML compliant
        # Colour code in the form of #00FF00 to be used. Handy for text effects.
        (r'\[color=#([0-9A-Fa-f]{6})\](.+?)\[/color\]', r'<font color="#\1">\2</font>'),

        # Video Linking Tags
        (r'\[yt\](.+?)\[/yt\]', bb_youtube_ol),
        (r'\[yt=(.+?)\](.+?)\[/yt\]', bb_youtube_name_ol),
        (r'\[gv\](.+?)\[/gv\]', bb_googlevideo_ol),

        # Demovibes specific tags
        (r'\[user\](.+?)\[/user\]', bb_user),
        (r'\[song\](\d+?)\[/song\]', bb_song),
        (r'\[artist\](\d+?)\[/artist\]', bb_artist),
        (r'\[artist\](.+?)\[/artist\]', bb_artistname),
        #(r'\[queue\](\d+?)\[/queue\]', bb_queue), # Looks annoying in OneLiner
        (r'\[flag\](.+?)\[/flag\]', bb_flag),
        (r'\[thread\](\d+?)\[/thread\]', bb_thread),
        (r'\[forum\](.+?)\[/forum\]', bb_forum),
        (r'\[group\](\d+?)\[/group\]', bb_group),
        (r'\[group\](.+?)\[/group\]', bb_groupname),
        (r'\[album\](\d+?)\[/album\]', bb_compilation),
        (r'\[compilation\](\d+?)\[/compilation\]', bb_compilation),
        (r'\[album\](.+?)\[/album\]', bb_compilation_name),
        (r'\[compilation\](.+?)\[/compilation\]', bb_compilation_name),
        (r'\[label\](\d+?)\[/label\]', bb_label),
        (r'\[label\](.+?)\[/label\]', bb_labelname),
        (r'\[platform\](\d+?)\[/platform\]', bb_platform),
        (r'\[platform\](.+?)\[/platform\]', bb_platformname),
    (r'\[faq\](\d+?)\[/faq\]', bb_faq),
      ]

bbdata_full = [
        (r'\[url\](.+?)\[/url\]', r'<a href="\1" target="_new">\1</a>'),
        (r'\[url=(.+?)\](.+?)\[/url\]', r'<a href="\1" target="_new">\2</a>'),
        (r'\[email\](.+?)\[/email\]', r'<a href="mailto:\1">\1</a>'),
        (r'\[email=(.+?)\](.+?)\[/email\]', r'<a href="mailto:\1">\2</a>'),
        (r'\[img\](.+?\.(jpg|jpeg|png|gif|bmp))\[/img\]', r'<img src="\1" alt="" />'),
        (r'\[img=(.+?)\](.+?\.(jpg|jpeg|png|gif|bmp))\[/img\]', r'<a href="\1" target="_new"><b>\2</b><br /><img src="\1" alt="" /></a>'),

        (r'\[b\](.+?)\[/b\]', r'<strong>\1</strong>'),
        (r'\[i\](.+?)\[/i\]', r'<i>\1</i>'),
        (r'\[u\](.+?)\[/u\]', r'<u>\1</u>'),
        (r'\[s\](.+?)\[/s\]', r'<s>\1</s>'),
        (r'\[quote=(.+?)\](.+?)\[/quote\]', r'<div class="bbquote"><b>\1 said:</b> "\2"</div>'),
        (r'\[quote\](.+?)\[/quote\]', r'<div class="bbquote"><b>Quote:</b> "\1"</div>'),
        (r'\[center\](.+?)\[/center\]', r'<div align="center">\1</div>'),
        (r'\[code\](.+?)\[/code\]', r'<tt class="bbcode">\1</tt>'),
        (r'\[big\](.+?)\[/big\]', r'<big>\1</big>'),
        (r'\[small\](.+?)\[/small\]', r'<small>\1</small>'),
        (r'\[size=(.+?)\](.+?)\[/size\]', bb_size),
        (r'\[pre\](.+?)\[/pre\]', r'<pre class="bbpre">\1</pre>'),

        (r'\[red\](.+?)\[/red\]', r'<font color="red">\1</font>'),
        (r'\[green\](.+?)\[/green\]', r'<font color="green">\1</font>'),
        (r'\[blue\](.+?)\[/blue\]', r'<font color="blue">\1</font>'),
        (r'\[black\](.+?)\[/black\]', r'<font color="black">\1</font>'),
        (r'\[brown\](.+?)\[/brown\]', r'<font color="brown">\1</font>'),
        (r'\[cyan\](.+?)\[/cyan\]', r'<font color="cyan">\1</font>'),
        (r'\[darkblue\](.+?)\[/darkblue\]', r'<font color="darkblue">\1</font>'),
        (r'\[gold\](.+?)\[/gold\]', r'<font color="gold">\1</font>'),
        (r'\[grey\](.+?)\[/grey\]', r'<font color="gray">\1</font>'),
        (r'\[magenta\](.+?)\[/magenta\]', r'<font color="magenta">\1</font>'),
        (r'\[orange\](.+?)\[/orange\]', r'<font color="orange">\1</font>'),
        (r'\[pink\](.+?)\[/pink\]', r'<font color="pink">\1</font>'),
        (r'\[purple\](.+?)\[/purple\]', r'<font color="purple">\1</font>'),
        (r'\[white\](.+?)\[/white\]', r'<font color="white">\1</font>'),
        (r'\[yellow\](.+?)\[/yellow\]', r'<font color="yellow">\1</font>'),
        (r'\[color=#(.+?)\](.+?)\[/color\]', r'<font color="#\1">\2</font>'),

        (r'\[table\](.+?)\[/table\]', r'<table class="bbtable">\1</table>'),
        (r'\[th\](.+?)\[/th\]', r'<th>\1</th>'),
        (r'\[td\](.+?)\[/td\]', r'<td>\1</td>'),
        (r'\[tr\](.+?)\[/tr\]', r'<tr>\1</tr>'),

        # Demovibes specific BB tags
        (r'\[user\](.+?)\[/user\]', bb_user),
        (r'\[song\](\d+?)\[/song\]', bb_song),
        (r'\[artist\](\d+?)\[/artist\]', bb_artist),
        (r'\[artist\](.+?)\[/artist\]', bb_artistname),
        (r'\[queue\](\d+?)\[/queue\]', bb_queue),
        (r'\[flag\](.+?)\[/flag\]', bb_flag),
        (r'\[thread\](\d+?)\[/thread\]', bb_thread),
        (r'\[forum\](.+?)\[/forum\]', bb_forum),
        (r'\[group\](\d+?)\[/group\]', bb_group),
        (r'\[group\](.+?)\[/group\]', bb_groupname),
        (r'\[album\](\d+?)\[/album\]', bb_compilation),
        (r'\[compilation\](\d+?)\[/compilation\]', bb_compilation),
        (r'\[album\](.+?)\[/album\]', bb_compilation_name),
        (r'\[compilation\](.+?)\[/compilation\]', bb_compilation_name),
        (r'\[label\](\d+?)\[/label\]', bb_label),
        (r'\[label\](.+?)\[/label\]', bb_labelname),
        (r'\[platform\](\d+?)\[/platform\]', bb_platform),
        (r'\[platform\](.+?)\[/platform\]', bb_platformname),
    (r'\[faq\](\d+?)\[/faq\]', bb_faq),

        # Experimental BBCode tags
        (r'\[youtube\](.+?)\[/youtube\]', bb_youtube),
        (r'\[gvideo\](.+?)\[/gvideo\]', bb_gvideo),
    ]

def make_smileys():

    def make_re(thesmiley):
        return re.compile(r'(?:^|(?<=\s|<|>|:))%s(?=$|\s|<|>|:)' % re.escape(thesmiley), re.IGNORECASE)

    r = []
    secretsmileys = getattr(settings,'SECRETSMILEYS', [])
    smileys = settings.SMILEYS
    for smiley in secretsmileys:
        sm = make_re(smiley[0])
        v = r'<img src="%s" title="%s" />' % (settings.MEDIA_URL + smiley[1], smiley[2])
        r.append((sm, v))
    for smiley in smileys:
        sm = make_re(smiley[0])
        v = r'<img src="%s" title="%s" />' % (settings.MEDIA_URL + smiley[1], smiley[0])
        r.append((sm, v))
    return r

SMILEYS = make_smileys()

def reify(bblist):
    templist = []
    for x in bblist:
        res = re.compile(x[0], re.DOTALL | re.IGNORECASE)
        templist.append((res, x[1]))
    return templist

#Creating list and compiling regex only once should
#give a small speed boost.
bbdata_full = reify(bbdata_full)
bbdata_oneliner = reify(bbdata_oneliner)

smileys.is_safe = True
bbcode.is_safe = True
bbcode_oneliner.is_safe = True
oneliner_mediaparse.is_safe = True
wordwrap.is_safe = True
get_rating_stars_song_avg.is_safe = True
dv_urlize.is_safe = True

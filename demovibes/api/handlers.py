from piston.handler import BaseHandler, AnonymousBaseHandler
from webview.models import Song, Queue, User, Artist, Userprofile, Oneliner, SongVote
from django import forms
from webview import common
from webview import forms as webforms
from piston.utils import validate, rc

#Re-used fields:
fUSER = ("user", ("username",))

class SongHandler(BaseHandler):
    """
    Fetch information about songs in database
    """
    allowed_methods = ('GET',)
    model = Song
    fields = (
        "status",
        "status_long",
        "id",
        "title",
        "rating",
        "rating_votes",
        ("uploader", (
            "username",
        )),
        "added",
        "license",
        "explicit",
        "bitrate",
        "song_length",
        "num_favorited",
        ("metadata", (
                "info",
                "pouetid",
                "remix_of_id",
                "ytvidid",
                "platform",
                ("artists",(
                    "id",
                    "handle",
                    "name",
                )),
                "groups",
                "labels",
                "type",
            )
        ),
    )

    def read(self, request, song_id):
        """
        Return info about song
        """
        song = Song.objects.get(id=song_id)
        song.status_long = song.get_status_display()
        song.metadata = song.get_metadata()
        return song

    @staticmethod
    def resource_uri():
        return ('api_song_handler', ['id'])

class ArtistHandler(BaseHandler):
    allowed_methods = ('GET',)
    model = Artist
    fields = ("id", "webpage", "status", "handle", "home_country",
            "is_deceased", "deceased_date", "name", "dob", "alias_of",
            "home_location", "info",
            ("get_songs", (
                "id",
                "title",
            )),
        )

    def read(self, request, artist_id):
        """
        Return info about artist
        """
        return Artist.objects.get(id=artist_id)

    @staticmethod
    def resource_uri():
        return ('api_artist_handler', ['id'])

class QueueSongForm(forms.Form):
    song = forms.ModelChoiceField(queryset=Song.objects.all())

fQ_common = (
    "requested",
    "eta",
    "time_played",
    ("song",
        ("title", "song_length", "rating")
    ),
    ("requested_by",
        ("username",)
    )
)
class BaseQueueHandler(object):
    """
    For handling the play queue
    """
    allowed_methods = ('GET',)
    model = Queue
    fields = (fQ_common)

    def read(self, request):
        """
        Get 20 latest songs in queue
        """
        up = Queue.objects.filter(played = False)
        dn = Queue.objects.filter(played = True).order_by("-id")[:20]
        return {'queue':up, 'played':dn}

    @staticmethod
    def resource_uri():
        return ('api_queue_handler2', [])

class AnonQueueHandler(BaseQueueHandler, AnonymousBaseHandler):
    pass

class AuthQueueHandler(BaseQueueHandler, BaseHandler):
    """
    For handling the play queue
    """
    allowed_methods = ('GET', 'POST')
    anonymous = AnonQueueHandler

    @validate(QueueSongForm)
    def create(self, request):
        """
        Queue given song

        Expect POST field "song" with the numeral id of the song to queue
        """
        song = request.POST.get("song")
        song = Song.objects.get(id=song)
        r = common.queue_song(song, request.user)
        return r

class UserBaseHandler(object):
    allowed_methods = ('GET',)
    model = User
    fields = ("username", "is_staff", "date_joined", "last_login", ("get_profile", ("country", "infoline", "web_page", "info", "location")))

    def read(self, request, username):
        """
        Return user information
        """
        user = User.objects.get(username=username)
        if user.get_profile().viewable_by(request.user):
            return user
        return rc.FORBIDDEN

    @staticmethod
    def resource_uri():
        return ('api_user_handler', ['username'])

class AnonUserHandler(UserBaseHandler, AnonymousBaseHandler):
    pass

class AuthUserHandler(UserBaseHandler, BaseHandler):
    anonymous = AnonUserHandler

class AuthProfile(BaseHandler):
    """
    Read and modify authenticated user's profile
    """
    allowed_methods = ('GET', 'PUT')
    model = Userprofile
    fields = webforms.ProfileForm.Meta.fields

    def read(self, request):
        """
        Show profile of authenticated user
        """
        return request.user.get_profile()

    @validate(webforms.ProfileForm)
    def update(self, request):
        """
        Update profile of authenticated user
        """
        userp = request.user.get_profile()
        profile = webforms.ProfileForm(request.PUT, instance=userp)
        profile.save()
        return rc.ALL_OK

    @staticmethod
    def resource_uri():
        return ('api_profile_handler', [])

class OnelinerForm(forms.Form):
    message = forms.CharField(max_length=256)

class BaseOnelinerHandler(object):
    """
    Handle oneliner access
    """
    model = Oneliner
    allowed_methods = ('GET',)
    fields = ["message", "added", fUSER]

    def read(self, request):
        """
        Get 20 latest oneliner entries
        """
        return Oneliner.objects.all()[:20]

    @staticmethod
    def resource_uri():
        return ('api_oneliner_handler', [])

class AnonOnelinerHandler(BaseOnelinerHandler, AnonymousBaseHandler):
    """
    Handle oneliner access

    Anonymous requests
    """
    pass

class AuthOnelinerHandler(BaseOnelinerHandler, BaseHandler):
    """
    Handle oneliner access

    Authenticated requests
    """
    anonymous = AnonOnelinerHandler
    allowed_methods = ('GET', 'POST')

    @validate(OnelinerForm)
    def create(self, request):
        """
        Post new oneliner.

        POST Data : "message"
        """
        line = request.POST.get("message")
        common.add_oneliner(request.user, line)
        return rc.CREATED

class VoteForm(forms.Form):
    vote = forms.ChoiceField(choices=(range(1, 6), range(1, 6)))

class BaseSongVotesHandler(object):
    """
    Handle data for song votes
    """
    model = SongVote
    allowed_methods = ('GET',)
    fields = ["vote", "added", fUSER]

    def read(self, request, song_id):
        """
        Get votes for song
        """
        song = Song.objects.get(id=song_id)
        return SongVote.objects.filter(song=song)

    @staticmethod
    def resource_uri():
        return ('api_votes_handler', ['id'])

class AnonSongVotesHandler(BaseSongVotesHandler, AnonymousBaseHandler):
    pass

class AuthSongVotesHandler(BaseSongVotesHandler, BaseHandler):
    allowed_methods = ('GET', "POST")
    anonymous = AnonSongVotesHandler
    @validate(VoteForm)
    def create(self, request, song_id):
        """
        Add or update vote on song

        POST values:
            vote : range 1-5
        """
        song = Song.objects.get(id=song_id)
        vote = int(request.POST.get("vote"))
        v = song.set_vote(vote, request.user)
        return v or rc.FORBIDDEN

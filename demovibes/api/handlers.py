from piston.handler import BaseHandler, AnonymousBaseHandler
from webview.models import Song, Queue, User, Artist, Userprofile
from django import forms
from webview import common
from webview import forms as webforms
from piston.utils import validate, rc

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

class BaseQueueHandler(object):
    """
    For handling the play queue
    """
    allowed_methods = ('GET',)
    model = Queue

    def read(self, request):
        """
        Get 20 latest songs in queue
        """
        return Queue.objects.all()[:20]

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

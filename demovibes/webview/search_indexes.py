import datetime
from haystack.indexes import *
from haystack import site
import webview.models as M

class ArtistIndex(SearchIndex):
    text = CharField(document=True, use_template=True)
    render = CharField(indexed=False, use_template=True)
    
    def get_queryset(self):
        return M.Artist.objects.all()

class SongIndex(SearchIndex):
    text = CharField(document=True, use_template=True)
    render = CharField(indexed=False, use_template=True)

    def get_queryset(self):
        return M.Song.objects.all()

site.register(M.Song, SongIndex)
site.register(M.Artist, ArtistIndex)

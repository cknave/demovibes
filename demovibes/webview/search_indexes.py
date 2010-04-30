import datetime
from haystack.indexes import *
from haystack import site
import webview.models as M

class SongIndex(SearchIndex):
    text = CharField(document=True, use_template=True)

    def get_queryset(self):
        return M.Song.objects.all()

site.register(M.Song, SongIndex)

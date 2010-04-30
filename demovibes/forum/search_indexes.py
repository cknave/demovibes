import datetime
from haystack.indexes import *
from haystack import site
import forum.models as M

class PostIndex(SearchIndex):
    text = CharField(document=True, use_template=True)

    def get_queryset(self):
        return M.Post.objects.all()

site.register(M.Post, PostIndex)

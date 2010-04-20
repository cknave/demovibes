from webview.models import *
from django import forms
from django.conf import settings
from PIL import Image
import mimetypes
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

class UploadForm(forms.ModelForm):
    class Meta:
        model = Song
        fields = ["title", "release_year", "file", "pouetid", "dtv_id", "wos_id", "zxdemo_id", "projecttwosix_id", "lemon_id", "hol_id", "al_id", "hvsc_url", "remix_of_id", "groups", "labels", "info", "type", "platform"]
        
    def clean_file(self):
        data = self.cleaned_data['file']
        mf = mad.MadFile(data)
        bitrate = mf.bitrate() / 1000
        layer = mf.layer()
        if hasattr(data, 'temporary_file_path'):
            F = data.temporary_file_path()
            mimetype, not_used = mimetypes.guess_type(F)
        else:
            mimetype = data.content_type
        if bitrate < 128 or layer != 3:
            raise forms.ValidationError("We only accept mpeg layer 3 (MP3) encoded files with bitrate of 128 kbps or higher")
        return data

class CreateArtistForm(forms.ModelForm):
    class Meta:
        model = Artist
        fields = ["handle", "name", "dob", "home_country", "home_location", "hol_id", "twitter_id", "last_fm_id", "info", "artist_pic", "webpage", "wiki_link", "groups", "labels"]

    def clean_artist_pic(self):
        artist_pic = self.cleaned_data['artist_pic']
        if not artist_pic:
            return None

        max_size = getattr(settings, 'MAX_ARTIST_AVATAR_SIZE', 65536)
        max_height = getattr(settings, 'MAX_ARTIST_AVATAR_HEIGHT', 250)
        max_width = getattr(settings, 'MAX_ARTIST_AVATAR_WIDTH', 250)

        if len(artist_pic) > max_size:
            raise forms.ValidationError('Image must be no bigger than %d bytes' % max_size)

        image = Image.open(artist_pic)
        img_w, img_h = image.size
        if img_w > max_width or img_h > max_height:
            raise forms.ValidationError('Image is bigger than allowed size dimensions! (Height : %d, width : %d)' % (max_height, max_width))

        return self.cleaned_data['artist_pic']
        
class CreateLabelForm(forms.ModelForm):
    class Meta:
        model = Label
        fields = ["name", "webpage", "wiki_link", "logo", "pouetid", "hol_id", "found_date", "cease_date", "info"]

    def clean_logo(self):
        logo = self.cleaned_data['logo']
        if not logo:
            return None

        max_size = getattr(settings, 'MAX_LABEL_AVATAR_SIZE', 65536)
        max_height = getattr(settings, 'MAX_LABEL_AVATAR_HEIGHT', 250)
        max_width = getattr(settings, 'MAX_LABEL_AVATAR_WIDTH', 250)

        if len(logo) > max_size:
            raise forms.ValidationError('Image must be no bigger than %d bytes' % max_size)

        image = Image.open(logo)
        img_w, img_h = image.size
        if img_w > max_width or img_h > max_height:
            raise forms.ValidationError('Image is bigger than allowed size dimensions! (Height : %d, width : %d)' % (max_height, max_width))

        return self.cleaned_data['logo']

class CreateGroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "group_logo", "webpage", "wiki_link", "pouetid", "found_date", "info"]

    def clean_group_logo(self):
        group_logo = self.cleaned_data['group_logo']
        if not group_logo:
            return None

        max_size = getattr(settings, 'MAX_GROUP_AVATAR_SIZE', 65536)
        max_height = getattr(settings, 'MAX_GROUP_AVATAR_HEIGHT', 250)
        max_width = getattr(settings, 'MAX_GROUP_AVATAR_WIDTH', 250)

        if len(group_logo) > max_size:
            raise forms.ValidationError('Image must be no bigger than %d bytes' % max_size)

        image = Image.open(group_logo)
        img_w, img_h = image.size
        if img_w > max_width or img_h > max_height:
            raise forms.ValidationError('Image is bigger than allowed size dimensions! (Height : %d, width : %d)' % (max_height, max_width))

        return self.cleaned_data['group_logo']

class ProfileForm(forms.ModelForm):
    def clean_avatar(self):
        avatar = self.cleaned_data['avatar']
        if not avatar:
            return None
        
        max_size = getattr(settings, 'MAX_AVATAR_SIZE', 65536)
        max_height = getattr(settings, 'MAX_AVATAR_HEIGHT', 100)
        max_width = getattr(settings, 'MAX_AVATAR_WIDTH', 100)

        if len(avatar) > max_size:
            raise forms.ValidationError('Image must be no bigger than %d bytes' % max_size)
        
        image = Image.open(avatar)
        img_w, img_h = image.size
        if img_w > max_width or img_h > max_height:
            raise forms.ValidationError('Image is bigger than allowed size dimensions! (Height : %d, width : %d)' % (max_height, max_width))
        return self.cleaned_data['avatar']
        
    class Meta:
        model = Userprofile
        fields = ['infoline', 'visible_to', 'web_page', 'aol_id', 'yahoo_id', 'icq_id', 'twitter_id', 'hol_id', 'country', 'location', 'avatar', 'info', 'fave_id', 'email_on_pm', 'email_on_group_add', 'email_on_artist_add', 'pm_accepted_upload', 'paginate_favorites', 'theme', 'custom_css']
        
class FlashUploadForm(forms.ModelForm):
    class Meta:
        model = Song
        fields = ["title",'pouetid', 'info', 'type', 'platform']
        
class PmForm(forms.ModelForm):
    to = forms.CharField()
    subject = forms.CharField(min_length=3)
    def clean_to(self):
        data = self.cleaned_data['to']
        try:
            U = User.objects.get(username=data)
        except:
            raise forms.ValidationError("User does not exist")
        return U
    class Meta:
        model = PrivateMessage
        fields = ('to', 'subject', 'message')

class CreateLinkForm(forms.ModelForm):
    class Meta:
        model = Link
        fields = ["link_type", "url_cat", "name", "link_title", "link_url", "link_image", "notes"]
        
    def clean_link_image(self):
        link_image = self.cleaned_data['link_image']
        if not link_image:
            return None

        max_size = getattr(settings, 'MAX_LINK_IMG_SIZE', 16384)
        max_height = getattr(settings, 'MAX_LINK_IMG_HEIGHT', 18)
        max_width = getattr(settings, 'MAX_LINK_IMG_WIDTH', 25)

        if len(link_image) > max_size:
            raise forms.ValidationError('Link Image must be no bigger than %d bytes' % max_size)

        image = Image.open(link_image)
        img_w, img_h = image.size
        if img_w > max_width or img_h > max_height:
            raise forms.ValidationError('Link Image is bigger than allowed size dimensions! (Height : %d, width : %d)' % (max_height, max_width))

        return self.cleaned_data['link_image']

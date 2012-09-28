from django.conf import settings

DOWNLOAD_LIMITS = getattr(settings, "SONG_DOWNLOAD_LIMIT", {})

def get_song_url(song, user):
    dltype = DOWNLOAD_LIMITS.get("TYPE")
    if dltype == "NGINX":
        return song.get_nginx_url()
    elif dltype == "CHEROKEE":
        return get_secure_download_url(song.file.url, user)
    else:
        return song.file.url

def get_current_download_limits_for(user):
    """
    Get current number of downloads left for user
    """
    limits = get_download_limit(user)
    if not limits:
        return (-1, -1)

    key = "urlgenlimit_%s" % user.id
    k = cache.get(key, 0)

    return (max(k+1 - limits.get("number", 0), 0), limits)

def download_limit_reached(user):
    """
    Check if a user's download limit is reached

    Return bool
    """
    l, total = get_current_download_limits_for(user)
    if l == 0:
        return True
    return False

def get_download_limit(user):
    """
    Get download limits for given user, and time window

    Returns {'seconds': int, 'number': int}
    """
    r = {}
    L = None

    limit = DOWNLOAD_LIMITS.get("LIMITS", {})

    if limit and user and user.is_authenticated():
        L = limit.get("default")

        if user.is_superuser and limit.get("admin"):
            L = limit.get("admin")
        elif user.is_staff and limit.get("staff"):
            L = limit.get("staff")
        for group in user.groups.all():
            gn = limit.get(group.name)
            if gn:
                if gn.get("seconds") >= L.get("seconds") and gn.get("number") >= L.get("number"):
                    L = gn
    if L:
        r['seconds'] = L.get("seconds", 60*60*24)
        r['number'] = L.get("number", 0)
    return r

def increase_downloads_for(user):
    """
    Add 1 to number of downloads for user
    """
    limits = get_download_limit(user)
    key = "urlgenlimit_%s" % user.id
    try:
        k = cache.incr(key)
    except:
        k = 1
        cache.set(key, k, limits.get("seconds"))
    if k > limits.get("number"):
        return None
    return True

def cherokee_secure_download (url, user=None):
    """
    Generate link for Cherokee secure download
    """
    cherokee_data = DOWNLOAD_LIMITS.get("CHEROKEE", {})
    if cherokee_data.get("KEY"):
        url = urllib.unquote(url)
        t = '%08x' % (time.time())
        if cherokee_data.get("REGEX"):
            try:
                url = str(url)
            except:
                url = url.encode("utf8")
            url = re.sub(*cherokee_data.get("REGEX") + (url,))
        mu = cherokee_data.get("PATH") + "/%s/%s/%s" % (hashlib.md5(cherokee_data.get("KEY") + "/" + url + t).hexdigest(), t, url)
        return mu.decode("utf8")
    return url

def get_secure_download_url(url, user=None):
    """
    Check if user have reached limit, return secure url or "limit reached" url or text
    """
    limit_reached = DOWNLOAD_LIMITS.get("LIMIT_REACHED_URL") or "Limit reached"
    if not verify_download_limit(user):
        return None
    if DOWNLOAD_LIMITS.get("CHEROKEE"):
        r = cherokee_secure_download(url, user)
    return r or limit_reached

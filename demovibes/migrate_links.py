def move(self, orm, model, linktype, field, url, name, rx):
    fname = "%s__isnull" % field
    kwargs = { fname : False}
    songs = model.objects.filter(**kwargs)
    if songs:
        gbl = orm.GenericBaseLink.objects.create(name=name, link=url, regex=rx, linktype=linktype)
        for s in songs:
            val = getattr(s, field)
            orm.GenericLink.objects.create(content_object=s, value=val, link=gbl)

def forwards(self, orm):
    gfk = generic.GenericForeignKey()
    gfk.contribute_to_class(orm.GenericLink, "content_object")

    "Write your forwards methods here."
    u = [
        (orm.Song, "S", "al_id", "http://www.atarilegend.com/games/games_detail.php?game_id=%linkval%", "Atari Legends", "\d+"),
        (orm.Song, "S", "cvgm_id", "http://www.cvgm.net/demovibes/song/%linkval%/", "CVGM SongID", "\d+"),
        (orm.Song, "S", "dtv_id", "http://www.demoscene.tv/prod.php?id_prod=%linkval%", "Demoscene.TV", "\d+"),
        (orm.Song, "S", "hol_id", "http://hol.abime.net/%linkval%", "Hall Of Light", "\d+"),
        (orm.Song, "S", "lemon_id", "http://www.lemon64.com/games/details.php?ID=%linkval%", "Lemon 64", "\d+"),
        (orm.Song, "S", "projecttwosix_id", "http://project2612.org/details.php?id=%linkval%", "Project2612", "\d+"),  
        (orm.Song, "S", "wos_id", "http://www.worldofspectrum.org/infoseekid.cgi?id=%linkval%", "World of Spectrum", "\d+"),
        (orm.Song, "S", "zxdemo_id", "http://zxdemo.org/item.php?id=%linkval%", "ZXDemo", "\d+"),
        #(orm.Song, "S", "_id", "%linkval%", "", "\d+"),
    ]
    for e in u:
        self.move(orm, *e)
        
print "This is unfinished. Exiting"

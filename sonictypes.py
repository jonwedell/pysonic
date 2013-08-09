#!/usr/bin/python

"""
* THIS SOFTWARE IS PROVIDED ''AS IS'' AND ANY
* EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
* WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
* DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY
* DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
* (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
* LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
* ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
* (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
* SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

# A song!
class song:
    """This class implements the logical concept of a song."""
    song_dict = None

    def __init__(self, song_dict, server=None):
        """We need the dictionary to create a song."""
        self.server = server
        if song_dict:
            self.song_dict = song_dict
        else:
            raise ValueError('You must pass the song dictionary to create a song.')

    def playSTR(self, jukebox=False):
        """If in jukebox mode, have subsonic add the song to the jukebox playlist. Otherwise return the playlist string"""
        if jukebox:
            self.server.subRequest(page="jukeboxControl", list_type='jukeboxStatus', extras={'action':'add', 'id':self.song_dict['id']})
        else:
            return "#EXTINF:" + self.song_dict.get('duration','?').encode('utf-8') + ',' + self.song_dict.get('artist','?').encode('utf-8') + ' - ' + self.song_dict.get('title','?').encode('utf-8') + "\n" + self.server.subRequest(page="stream", extras={'id':self.song_dict['id']}) + "\n"

    def __str__(self):
        return "      " + self.song_dict.get('id','?').encode('utf-8') + ": " + self.song_dict.get('title','?').encode('utf-8')

# An album!
class album:
    """This class implements the logical concept of an album."""
    album_dict = None
    songs = []

    def __init__(self, album_dict, server=None):
        """We need the dictionary to create an album."""
        self.songs = []
        self.server = server
        if album_dict:
            self.album_dict = album_dict
            songs = self.server.subRequest(page="getAlbum", list_type='song', extras={'id':self.album_dict['id']})
            sys.stdout.write('.')
            sys.stdout.flush()
            for one_song in songs:
                self.songs.append(song(one_song.attrib, server=self.server))
            self.songs = sorted(self.songs, key=lambda k: k.song_dict.get('track','0'))
        else:
            raise ValueError('You must pass the album dictionary to create an album.')

    def playSTR(self, jukebox=False):
        """Either return the needed playlist data, or run the command to add the song to the jukebox"""
        playlist = ""

        if jukebox:
            for one_song in self.songs:
                playlist += one_song.playSTR()
            return playlist
        else:
            for one_song in self.songs:
                playlist += one_song.playSTR()
            return playlist

    def recursivePrint(self, level=5):
        """Prints children up to level n"""
        res = "   " + self.album_dict.get('id','?').encode('utf-8') + ": " + self.album_dict.get('name','?').encode('utf-8')
        if level > 0:
            for one_song in self.songs:
                res += "\n" + one_song.__str__()
        return res

    # Implement expected methods
    def __iter__(self):
        return iter(self.songs)
    def __len__(self):
        return len(self.songs)
    def __str__(self):
        return self.recursivePrint(1)


# An artist!
class artist:
    """This class implements the logical concept of an artist."""
    artist_dict = None
    albums = []

    def addAlbums(self, albums):
        """Add any number of albums to the artist"""
        for one_album in albums:
            self.albums.append(album(one_album.attrib, server=self.server))

    def __init__(self, artist_dict, server=None):
        """We need the dictionary to create an artist."""
        self.albums = []
        self.server = server
        if artist_dict:
            artist_dict = artist_dict.getchildren()
            if len(artist_dict) == 1:
                self.artist_dict = artist_dict[0].attrib
                self.addAlbums(artist_dict[0].getchildren())
            else:
                raise ValueError('The root you passed includes more than one artist.')
            self.albums = sorted(self.albums, key=lambda k: k.album_dict.get('id','0'))
        else:
            raise ValueError('You must pass the artist dictionary to create an artist.')

    def playSTR(self, jukebox=False):
        """Either return the needed playlist data, or run the command to add the song to the jukebox"""
        playlist = ""

        if jukebox:
            for one_album in self.albums:
                playlist += one_album.playSTR()
            return playlist
        else:
            for one_album in self.albums:
                playlist += one_album.playSTR()
            return playlist

    def recursivePrint(self, level=5):
        """Prints children up to level n"""
        res = self.artist_dict.get('id','?').encode('utf-8') + ": " + self.artist_dict.get('name','?').encode('utf-8')
        if level > 0:
            for one_album in self.albums:
                res += "\n" + one_album.recursivePrint(level-1)
        return res

    # Implement expected methods
    def __iter__(self):
        return iter(self.albums)
    def __len__(self):
        return len(self.albums)
    def __str__(self):
        return self.recursivePrint(0)

# A list of artists!
class library:
    """This class implements the logical concept of a library."""
    artists = []
    initialized = False

    def addArtist(self, root):
        """Add an artist to the library"""
        self.artists.append(artist(root, server=self.server))

    def fillArtists(self, root):
        """Query the server for all the artists and albums"""
        for one_artist in state.artists:
            self.server.subRequest(page="getArtist", list_type='album', extras={'id':one_artist.attrib['id']})
            self.addArtist(state.prevroot)
        self.initialized = True

    def __init__(self, server=None):
        self.artists = []
        self.server = server

    def playSTR(self, mylist=None, jukebox=False):
        """Either return the needed playlist data, or run the command to add the song to the jukebox"""

        res_string = ""
        num_ret = 0

        if mylist:
            for item in mylist:
                res_string += item.playSTR()
                num_ret += 1
            return (res_string, num_ret)
        else:
            for item in self.prev_res:
                res_string += item.playSTR()
                num_ret += 1
            return (res_string, num_ret)

        if jukebox:
            playlist = ""
            for one_artist in self.artists:
                playlist += one_artist.playSTR()
            return playlist
        else:
            for one_artist in self.artists:
                one_artist.playSTR()

    def recursivePrint(self, level=5):
        """Prints children up to level n"""
        res = ""
        if level > 0:
            for one_artist in self.artists:
                res += "\n" + one_artist.recursivePrint(level-1)
        return res

    def getSongs(self):
        """Return a list of all songs in the library"""
        ret_songs = []
        for one_artist in self:
            for one_album in one_artist:
                for one_song in one_album:
                    ret_songs.append(one_song)
        return ret_songs

    def getAlbums(self):
        """Return a list of all albums in the library"""
        ret_albums = []
        for one_artist in self:
            for one_album in one_artist:
                ret_albums.append(one_album)
        return ret_albums

    def getArtists(self):
        """Return a list of all artists in the library"""
        return self.artists

    def searchSongs(self, search=None, key='title'):
        if search:
            res = []
            for one_song in self.getSongs():
                if search.lower() in one_song.song_dict[key].lower():
                    res.append(one_song)
        else:
            res = self.getSongs()

        self.prev_res = res
        return res

    def searchAlbums(self, search=None, key='name'):
        if search:
            res = []
            for one_album in self.getAlbums():
                if search.lower() in one_album.album_dict[key].lower():
                    res.append(one_album)
        else:
            res = self.getAlbums()

        self.prev_res = res
        return res

    def searchArtists(self, search=None, key='name'):
        if search:
            res = []
            for one_artist in self.getArtists():
                if search.lower() in one_artist.artist_dict[key].lower():
                    res.append(one_artist)
        else:
            res = self.getArtists()

        self.prev_res = res
        return res

    # Implement expected methods
    def __iter__(self):
        return iter(self.artists)
    def __len__(self):
        return len(self.artists)
    def __str__(self):
        return self.recursivePrint(1)

# A server!
class server:
    """This class represents a server. It stores the password and makes queries."""

    def __init__(self, servername, username, password, server, jukebox=False):
        # Build the default parameters into a reusable hash
        self.default_params = {
          'u': username,
          'p': "enc:" + password.encode("hex"),
          'v': "1.9.0",
          'c': "subsonic-cli",
          'f': "xml"
        }

        # Clean up the server address
        if server.count(".") == 0:
            server += ".subsonic.org"
        if server[0:7] != "http://" and server[0:8] != "https://":
            server = "http://" + server
        server = server + "/rest/"
        self.server = server
        self.jukebox = jukebox
        self.servername = servername
        self.pickle = os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic", self.servername + ".pickle"))
        self.library = library(server=self)

    def __str__(self):
        return "URL: " + self.server + "\nJukebox: " + str(self.jukebox) + "\nParameters: " + str(self.default_params)

    def checkError(self, root):
        """Use this to check to see if we got a valid result from the subsonic server"""
        if root.attrib['status'] != 'ok':
            print "Error: " + root[0].attrib['message']
            return int(root[0].attrib['code'])
        return 0

    def subRequest(self, page="ping", list_type='subsonic-response', extras={}):
        """Query subsonic, parse resulting xml and return an ElementTree"""
        params = self.default_params.copy()
        # Add request specific parameters to our hash
        for keys in extras:
            params[keys] = extras[keys]

        # Encode our parameters and send the request
        params = urllib.urlencode(params)

        # To stream we only want the URL returned, not the data
        if page == "stream":
            return self.server+page+"?"+params

        # Get the server response
        try:
            stringres = urllib2.urlopen(self.server+page,params).read()
        except urllib2.URLError as e:
            print "Error: %s" % e
            sys.exit(5)

        if options.verbose:
            print stringres

        # Parse the XML
        root = ET.fromstring(stringres)
        # Make sure the result is valid
        if self.checkError(root):
            return "err"

        # Store what type of result this is
        state.idtype = list_type
        state.prevroot = root

        # Return a list of the elements with the specified type
        return list(root.getiterator(tag='{http://subsonic.org/restapi}'+list_type))

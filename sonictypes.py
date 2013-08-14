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

    def playSTR(self):
        """If in jukebox mode, have subsonic add the song to the jukebox playlist. Otherwise return the playlist string"""
        if self.server.jukebox:
            self.server.subRequest(page="jukeboxControl", list_type='jukeboxStatus', extras={'action':'add', 'id':self.song_dict['id']})
        else:
            return "#EXTINF:" + self.song_dict.get('duration','?').encode('utf-8') + ',' + self.song_dict.get('artist','?').encode('utf-8') + ' - ' + self.song_dict.get('title','?').encode('utf-8') + "\n" + self.server.subRequest(page="stream", extras={'id':self.song_dict['id']}) + "\n"

    def __str__(self):
        return "%-3s: %s\n   %-4s: %s\n      %-5s: %s" % \
                                                (self.song_dict.get('artistId','?').encode('utf-8'), self.song_dict.get('artist','?').encode('utf-8')[0:getWidth(5)],\
                                                self.song_dict.get('albumId','?').encode('utf-8'), self.song_dict.get('album','?').encode('utf-8')[0:getWidth(9)],\
                                                self.song_dict.get('id','?').encode('utf-8'), self.song_dict.get('title','?').encode('utf-8')[0:getWidth(13)])

    def recursivePrint(self, level=5, indentations=0):
        """Prints children up to level n"""
        res = "%-5s: %s"
        if indentations > 0:
            res = "   "*indentations + res
        return res % (self.song_dict.get('id','?').encode('utf-8'), self.song_dict.get('title','?').encode('utf-8')[0:getWidth(7+3*indentations)])

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
            # Sort the songs by track number
            self.songs = sorted(self.songs, key=lambda k: k.song_dict.get('track','0'))
        else:
            raise ValueError('You must pass the album dictionary to create an album.')

    def playSTR(self):
        """Either return the needed playlist data, or run the command to add the song to the jukebox"""

        if self.server.jukebox:
            for one_song in self.songs:
                one_song.playSTR()
        else:
            playlist = ""
            for one_song in self.songs:
                playlist += one_song.playSTR()
            return playlist

    def recursivePrint(self, level=5, indentations=0):
        """Prints children up to level n"""
        res = "%-4s: %s"
        if indentations > 0:
            res = "   "*indentations + res
        if level > 0:
            for one_song in self.songs:
                res += "\n" + one_song.recursivePrint(level-1, indentations+1)
        return res % (self.album_dict.get('id','?').encode('utf-8'), self.album_dict.get('name','?').encode('utf-8')[0:getWidth(6+3*indentations)])

    # Implement expected methods
    def __iter__(self):
        return iter(self.songs)
    def __len__(self):
        return len(self.songs)
    def __str__(self):
        return "%-3s: %s\n" % (self.album_dict.get('artistId','?').encode('utf-8'), self.album_dict.get('artist','?').encode('utf-8')[0:getWidth(5)]) + self.recursivePrint(1,1)


# An artist!
class artist:
    """This class implements the logical concept of an artist."""
    artist_dict = None
    albums = []

    def addAlbums(self, albums):
        """Add any number of albums to the artist"""
        for one_album in albums:
            self.albums.append(album(one_album.attrib, server=self.server))

    def __init__(self, artist_id=None, server=None):
        """We need the dictionary to create an artist."""
        self.albums = []
        self.server = server

        if artist_id is not None:
            # Fetch the whole XML tree for this artist
            artist_dict = self.server.subRequest(page="getArtist", list_type='album', extras={'id':artist_id}, retroot=True)

            if artist_dict == "err":
                return None

            if len(artist_dict) == 1:
                self.artist_dict = artist_dict[0].attrib
                self.addAlbums(artist_dict[0].getchildren())
            else:
                print artist_dict
                raise ValueError('The root you passed includes more than one artist.')
            # Sort the albums by ID
            self.albums = sorted(self.albums, key=lambda k: k.album_dict.get('id','0'))
        else:
            raise ValueError('You must pass the artist dictionary to create an artist.')

    def playSTR(self):
        """Either return the needed playlist data, or run the command to add the song to the jukebox"""

        if self.server.jukebox:
            for one_album in self.albums:
                one_album.playSTR()
        else:
            playlist = ""
            for one_album in self.albums:
                playlist += one_album.playSTR()
            return playlist

    def recursivePrint(self, level=3, indentations=0):
        """Prints children up to level n"""
        res = "%-3s: %s"
        if indentations > 0:
            res = "   "*indentations + res
        if level > 0:
            for one_album in self.albums:
                res += "\n" + one_album.recursivePrint(level-1, indentations+1)
        return res % (self.artist_dict.get('id','?').encode('utf-8'), self.artist_dict.get('name','?').encode('utf-8')[0:getWidth(5+3*indentations)])

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

    def addArtist(self, artist_id):
        """Add an artist to the library"""
        new_artist = artist(artist_id, server=self.server)
        if new_artist:
            self.artists.append(new_artist)

    def updateIDS(self):
        self.album_ids = map(lambda x:x.album_dict['id'], self.getAlbums())
        self.artist_ids = map(lambda x:x.artist_dict['id'], self.getArtists())

    def updateLib(self):
        """Check for new albums and artists"""

        self.updateIDS()
        new_albums = self.server.subRequest(page="getAlbumList2", list_type='album', extras={'type':'newest', 'size':500})

        for one_album in new_albums:
            if not one_album.attrib['artistId'] in self.artist_ids:
                sys.stdout.write("Adding artist " + one_album.attrib['artist'].encode('utf-8') + ": ")
                sys.stdout.flush()
                self.addArtist(one_album.attrib['id'])
                self.updateIDS()
            elif not one_album.attrib['id'] in self.album_ids:
                sys.stdout.write("Adding album " + one_album.attrib['name'].encode('utf-8') + " to artist " + one_album.attrib['artist'].encode('utf-8') + ": ")
                sys.stdout.flush()
                self.getArtistById(one_album.attrib['artistId']).addAlbums(one_album)
                self.updateIDS()

    def fillArtists(self):
        """Query the server for all the artists and albums"""
        for one_artist in self.server.subRequest(page="getArtists", list_type='artist'):
            self.addArtist(one_artist.attrib['id'])
        self.initialized = True

    def __init__(self, server=None):
        self.artists = []
        self.server = server

    def playSTR(self, mylist=None, jukebox=False):
        """Either return the needed playlist data, or run the command to add the song to the jukebox"""

        # Make sure they have something to play
        if not hasattr(self,'prev_res') or not self.prev_res:
            return ("", 0)

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
                num_ret += 1
            return (playlist, num_ret)
        else:
            for one_artist in self.artists:
                one_artist.playSTR()

    def recursivePrint(self, level=5, indentations=0):
        """Prints children up to level n"""
        res = ""
        if indentations > 0:
            res = "   "*indentations
        if level > 0:
            for one_artist in self.artists:
                res += "\n" + one_artist.recursivePrint(level-1, indentations+1)
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

    def getSongById(self, song_id):
        """Fetch a song from the library based on it's id"""
        for one_song in self.getSongs():
            if one_song.song_dict['id'] == song_id:
                self.prev_res = [one_song]
                return one_song
        self.prev_res = []
        return None

    def getArtistById(self, artist_id):
        """Return an artist based on ID"""
        for one_artist in self.getArtists():
            if one_artist.artist_dict['id'] == artist_id:
                return one_artist
        return None

    def searchSongs(self, search=None):
        """Search through song names or ids for the query"""
        if search:
            res = []
            for one_song in self.getSongs():
                if search.isdigit():
                    if one_song.song_dict['id'] == search:
                        res.append(one_song)
                else:
                    if search.lower() in one_song.song_dict['title'].lower():
                        res.append(one_song)
        else:
            res = self.getSongs()

        self.prev_res = res
        return res

    def searchAlbums(self, search=None):
        """Search through albums names or ids for the query"""
        if search:
            res = []
            for one_album in self.getAlbums():
                if search.isdigit():
                    if one_album.album_dict['id'] == search:
                        res.append(one_album)
                else:
                    if search.lower() in one_album.album_dict['name'].lower():
                        res.append(one_album)
        else:
            res = self.getAlbums()

        self.prev_res = res
        return res

    def searchArtists(self, search=None):
        """Search through artists names or ids for the query"""
        if search:
            res = []

            for one_artist in self.getArtists():
                if search.isdigit():
                    if one_artist.artist_dict['id'] == search:
                        res.append(one_artist)
                else:
                    if search.lower() in one_artist.artist_dict['name'].lower():
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
        return self.recursivePrint(1,-1)

# A server!
class server:
    """This class represents a server. It stores the password and makes queries."""

    def __init__(self, servername, username, password, server_url, enabled=True, jukebox=False):
        # Build the default parameters into a reusable hash
        self.default_params = {
          'u': username,
          'v': "1.9.0",
          'p': "enc:" + password.encode("hex"),
          'c': "subsonic-cli",
          'f': "xml"
        }

        # If the password is already hex encoded don't recode it
        if password[0:4] == "enc:":
            self.default_params['p'] = password

        # Clean up the server address
        if server_url.count(".") == 0:
            server_url += ".subsonic.org"
        if server_url[0:7] != "http://" and server_url[0:8] != "https://":
            server_url = "http://" + server_url
        if server_url[-6:] != "/rest/":
            server_url = server_url + "/rest/"
        self.server_url = server_url
        self.jukebox = jukebox
        self.servername = servername
        self.enabled = enabled
        self.online = False
        self.pickle = os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic", self.servername + ".pickle"))
        self.library = library(server=self)

    def printConfig(self):
        return "[%s]\nHost: %s\nUsername: %s\nPassword: %s\nJukebox: %s\nEnabled: %s\n\n" % (self.servername, self.server_url, self.default_params['u'], \
                self.default_params['p'], str(self.jukebox), str(self.enabled))

    def __str__(self):
        return self.printConfig()

    def subRequest(self, page="ping", list_type='subsonic-response', extras={}, timeout=10, retroot=False):
        """Query subsonic, parse resulting xml and return an ElementTree"""
        params = self.default_params.copy()
        # Add request specific parameters to our hash
        for keys in extras:
            params[keys] = extras[keys]

        # Encode our parameters and send the request
        params = urllib.urlencode(params)

        # To stream we only want the URL returned, not the data
        if page == "stream":
            return self.server_url+page+"?"+params

        if options.verbose:
            print self.server_url+page+"?"+params

        # Get the server response
        try:
            stringres = urllib2.urlopen(self.server_url+page,params, timeout=timeout).read()
        except urllib2.URLError as e:
            sys.stdout.write("Error: " + str(e) + "\n")
            sys.stdout.flush()
            return 'err'

        # Parse the XML
        root = ET.fromstring(stringres)

        if options.verbose:
            print stringres
            print root

        # Make sure the result is valid
        if root.attrib['status'] != 'ok':
            sys.stdout.write("Error: " + root[0].attrib['message'] + "\n")
            sys.stdout.flush()
            return 'err'

        # Short circuit return the whole tree if requested
        if retroot:
            return root

        # Return a list of the elements with the specified type
        return list(root.getiterator(tag='{http://subsonic.org/restapi}'+list_type))

    def goOnline(self):
        """Ping the server to ensure it is online, if it is load the pickle or generate the local cache if necessary"""
        sys.stdout.write("Checking if server " + self.servername + " is online: ")
        sys.stdout.flush()
        online = self.subRequest(timeout=2)

        # Don't add the server to our server list if it crashes out
        if online == 'err':
            self.online = False
            return

        self.online = True
        sys.stdout.write('Yes\n')
        sys.stdout.flush()

        # Try to load the pickle, build the library if neccessary
        try:
            self.library = pickle.load(open(self.pickle,"rb"))
        except IOError:
            sys.stdout.write("Building library.")
            self.library.fillArtists()
            pickle.dump(self.library, open(self.pickle,"w"), 2)
            print ""

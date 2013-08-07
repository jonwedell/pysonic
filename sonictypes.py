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

    # Constructor
    def __init__(self, song_dict):
        """We need the dictionary to create a song."""
        if song_dict:
            self.song_dict = song_dict
        else:
            raise ValueError('You must pass the song dictionary to create a song.')

    # Either return the needed playlist data, or run the command to add the song to the jukebox
    def play(self, jukebox=False):
        """If in jukebox mode, have subsonic add the song to the jukebox playlist. Otherwise return the playlist string"""
        if jukebox:
            subRequest(page="jukeboxControl", list_type='jukeboxStatus', extras={'action':'add', 'id':self.song_dict['id']})
        else:
            return "#EXTINF:" + self.song_dict.get('duration','?').encode('utf-8') + ',' + self.song_dict.get('artist','?').encode('utf-8') + ' - ' + self.song_dict.get('title','?').encode('utf-8') + "\n" + subRequest(page="stream", extras={'id':self.song_dict['id']}) + "\n"

    # Print sensibly
    def __str__(self):
        return "      " + self.song_dict.get('id','?').encode('utf-8') + ": " + self.song_dict.get('title','?').encode('utf-8')

# An album!
class album:
    """This class implements the logical concept of an album."""
    album_dict = None
    songs = []

    def __init__(self, album_dict):
        """We need the dictionary to create an album."""
        self.songs = []
        if album_dict:
            self.album_dict = album_dict
            listAlbum(query=self.album_dict['id'], printy=False)
            sys.stdout.write('.')
            sys.stdout.flush()
            for one_song in state.previous_result[:]:
                self.songs.append(song(one_song.attrib))
        else:
            raise ValueError('You must pass the album dictionary to create an album.')

    # Either return the needed playlist data, or run the command to add the song to the jukebox
    def play(self, jukebox=False):
        playlist = ""
        for one_song in self.songs:
            playlist += one_song.play()
        return playlist

    # Implement expected methods
    def __iter__(self):
        return iter(self.songs)
    def __len__(self):
        return len(self.songs)
    def __str__(self):
        res = "   " + self.album_dict.get('id','?').encode('utf-8') + ": " + self.album_dict.get('name','?').encode('utf-8')
        for song in self.songs:
            res += "\n" + song.__str__()
        return res


# An artist!
class artist:
    """This class implements the logical concept of an artist."""
    artist_dict = None
    albums = []

    def addAlbums(self, albums):
        """Add any number of albums to the artist"""
        for one_album in albums:
            self.albums.append(album(one_album.attrib))

    def __init__(self, artist_dict):
        """We need the dictionary to create an artist."""
        self.albums = []
        if artist_dict:
            artist_dict = artist_dict.getchildren()
            if len(artist_dict) == 1:
                self.artist_dict = artist_dict[0].attrib
                self.addAlbums(artist_dict[0].getchildren())
            else:
                raise ValueError('The root you passed includes more than one artist.')
        else:
            raise ValueError('You must pass the artist dictionary to create an artist.')

    # Either return the needed playlist data, or run the command to add the song to the jukebox
    def play(self, jukebox=False):
        playlist = ""
        for one_album in self.albums:
            playlist += one_album.play()
        return playlist

    # Implement expected methods
    def __iter__(self):
        return iter(self.albums)
    def __len__(self):
        return len(self.albums)
    def __str__(self):
        res = self.artist_dict.get('id','?').encode('utf-8') + ": " + self.artist_dict.get('name','?').encode('utf-8')
        for album in self.albums:
            res += "\n" + album.__str__()
        return res

# A list of artists!
class library:
    """This class implements the logical concept of a library."""
    artists = []
    initialized = False

    def addArtist(self, root):
        """Add an artist to the library"""
        self.artists.append(artist(root))

    # Fill ourselves out
    def fillArtists(self, root):
        for one_artist in state.artists:
            listArtist(query=one_artist.attrib['id'], printy=False)
            self.addArtist(state.prevroot)
        self.initialized = True

    def __init__(self):
        self.artists = []

    # Either return the needed playlist data, or run the command to add the song to the jukebox
    def play(self, jukebox=False):
        playlist = ""
        for one_artist in self.artists:
            playlist += one_artist.play()
        return playlist

    # Implement expected methods
    def __iter__(self):
        return iter(self.artists)
    def __len__(self):
        return len(self.artists)
    def __str__(self):
        res = ""
        for artist in self.artists:
            res += "\n" + artist.__str__()
        return res

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
        self.library = library()

    def __str__(self):
        return "URL:" + server.server + "\nJukebox:" + self.jukebox + "\nParameters: " + str(self.default_params)

    # Use this to check to see if we got a valid result
    def checkError(self, root, fatal=False):
        if root.attrib['status'] != 'ok':
            print "Error: " + root[0].attrib['message']
            if fatal:
                sys.exit(int(root[0].attrib['code']))
            else:
                return int(root[0].attrib['code'])
        return 0

    # Query subsonic, parse resulting xml and return an ElementTree
    def subRequest(self, page="ping", list_type='subsonic-response', extras={}, fatal_errors=False):
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
            if fatal_errors:
                sys.exit(5)
            state.idtype = ''
            return []

        # Parse the XML
        root = ET.fromstring(stringres)
        # Make sure the result is valid
        self.checkError(root, fatal=fatal_errors)

        # Store what type of result this is
        state.idtype = list_type
        state.prevroot = root

        # Return a list of the elements with the specified type
        return list(root.getiterator(tag='{http://subsonic.org/restapi}'+list_type))

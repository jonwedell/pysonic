#!/usr/bin/python

"""
Coded by Jon Wedell

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

import os
import sys
import time
import stat
import random
import urllib
import urllib2
import getpass
import readline
import tempfile
import subprocess
import ConfigParser
import cPickle as pickle
import xml.etree.ElementTree as ET
from optparse import OptionParser, OptionGroup

def getHome(filename=None):
    if filename:
        return os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic",filename))
    else:
        return os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic/"))

def getWidth(used=0):
    """Get the remaining width of the terminal"""

    # Only update the width of the terminal every 5 seconds (otherwise we will fork a gazillion processes)
    if not hasattr(state, 'cols') or state.coltime + 5 < time.time():

        # Check if we are outputting to a terminal style device
        mode = os.fstat(0).st_mode
        if stat.S_ISFIFO(mode) or stat.S_ISREG(mode):
            state.cols = 10000
        else:
            state.cols = os.popen('stty size', 'r').read().split()[1]
        # Update the setting time
        state.coltime = time.time()

    # Return the remaining terminal width
    return int(state.cols)-used

def getMessages():
    """Get chat messages"""
    for one_server in state.server:
        print "On server: " + one_server.servername
        messages =one_server.subRequest(page="getChatMessages", list_type='chatMessage')
        # Convert time from unix time to readable time
        for message in messages:
            message.attrib['time'] = time.ctime(float(message.attrib['time'])/1000).rstrip()
            print "   At %s %s wrote %s." % (message.attrib.get('time','?'), message.attrib.get('username','?'), message.attrib.get('message','?'))

def writeMessage(message):
    """Write a chat message"""
    for one_server in state.server:
        print "On server: " + one_server.servername
        messages = one_server.subRequest(page="addChatMessage", list_type='subsonic-response', extras={'message':message})
        if messages[0].attrib['status'] == 'ok':
            print "   Successfully wrote message: '" + str(message) + "'"

def nowPlaying():
    """Get the now playing lists"""
    for one_server in state.server:
        print "On server: " + one_server.servername
        playing = one_server.subRequest(page="getNowPlaying", list_type='entry')
        for one_person in playing:
            print "   %s minutes ago %s played %s by %s (ID:%s)" % \
                (one_person.attrib.get('minutesAgo','?'), one_person.attrib.get('username','?'), \
                one_person.attrib.get('title','?'), one_person.attrib.get('artist','?'), one_person.attrib.get('id','?'))
            one_server.library.getSongById(one_person.attrib['id'])

def stopPlaying():
    """Kill whatever is playing the media"""
    p = subprocess.Popen([options.player, "--one-instance", "--no-playlist-enqueue", "vlc://quit"], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    p.wait()

def chooseServer(query=None):
    """Choose whether to display one server or all servers"""
    if query == "all":
        state.server = []
        for one_server in state.all_servers:
            if not one_server.enabled:
                one_server.enabled = True
            if not one_server.online:
                one_server.goOnline()
            if one_server.online:
                state.server.append(one_server)
        print "Using server(s): " + str(",".join(map(lambda x:x.servername, state.server)))
    elif query:
        queries = query.replace(","," ").split()
        myres = []
        serv_hash = {}
        for x in state.all_servers:
            serv_hash[x.servername] = x
        for query in queries:
            if query in serv_hash:
                one_server = serv_hash[query]
                if not one_server.enabled:
                    one_server.enabled = True
                if not one_server.online:
                    one_server.goOnline()
                if one_server.online:
                    myres.append(one_server)
                    print "Selected server " + query + "."
            else:
                print "No matching server (" + query + ")! Choose from: " + str(",".join(map(lambda x:x.servername, state.all_servers)))
        if len(myres) > 0:
            state.server = myres
        else:
            print "No servers matched your results."
        print "Using server(s): " + str(",".join(map(lambda x:x.servername, state.server)))
        # Make sure that only enabled servers are enabled
        for one_server in state.all_servers:
            one_server.enabled = False
        for one_server in state.server:
            one_server.enabled = True
    else:
        if len(state.server) == len(state.all_servers):
            print "All servers enabled. Enter a server name to choose that server."
            print "Choose from: " + str(",".join(map(lambda x:x.servername, state.all_servers)))
        else:
            print "Currently active servers: " + str(",".join(map(lambda x:x.servername, state.server)))
            print "All known servers: " + str(",".join(map(lambda x:x.servername, state.all_servers)))
            print "Type 'server all' to restore all servers, or enter server names to select."

def playPrevious(play=False):
    """Play whatever the previous result was"""

    # Count the number of results
    results = 0

    # Build the basic VLC args
    vlc_args = [options.player, "--one-instance"]
    vlc_args.append("--no-playlist-enqueue") if play else vlc_args.append("--playlist-enqueue")

    # Get the play string
    playlist = ""
    for one_server in state.server:
        res = one_server.library.playSTR()
        results += res[1]
        playlist += res[0]

    # Make sure there is something to play
    if results == 0:
        print "Last command did not result in anything playable."
        return

    # Create the m3u file
    playlist_file = os.path.join(tempfile.gettempdir(), str(time.time())[-10:-3] + ".m3u")
    vlc_args.append(playlist_file)
    playlistf = open(playlist_file, "w")
    playlistf.write("#EXTM3U\n")
    playlistf.write(playlist)
    playlistf.close()

    # Launch the music in VLC
    subprocess.Popen(vlc_args, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

def live(arg=None):
    """Enter python terminal"""
    if arg:
        exec(arg)
    else:
        import code
        vars = globals()
        vars.update(locals())
        shell = code.InteractiveConsole(vars)
        shell.interact()

def pickleLibrary(server):
    # Don't save the server information in the pickle
    server.library.updateServer(None)
    # Dump the pickle
    pickle.dump(server.library, open(server.pickle,"w"), 2)

def gracefulExit():
    """Quit gracefully, saving state"""

    # By forking, we can seem to quit right away but take a few moments
    #  to finish writing our state to disk
    pid = os.fork()

    if pid == 0:
        # Create the history file if it doesn't exist
        if not os.path.isfile(getHome("history")):
            open(getHome("history"), "a").close()
        readline.write_history_file(getHome("history"))

        # Write the current servers to the config file
        config = ""
        for server in state.all_servers:
            config += server.printConfig()
        open(getHome("config"), 'w').write(config)

        # Pickle the libraries
        for server in state.server:
            pickleLibrary(server)

        sys.exit(0)
    else:
        print " See ya!"
        sys.exit(0)

def addServer():
    """Interactively add a new server"""
    user_input_maps = {'y':True, 'yes':True, 't':True, 'true':True, 'n':False, 'no':True, 'f':False, 'false':False}

    servername = ''.join(raw_input("Informal name (one word is best): ").split())
    server_url = raw_input("URL or subsonic username: ")
    username = raw_input("Username: ")
    print "Press enter to use secure password mode. (Prompt for password each start.)"
    password = getpass.getpass()
    enabled = user_input_maps.get(raw_input("Enabled (y/n): ").lower(),True)
    jukebox = user_input_maps.get(raw_input("Jukebox mode (y/n): ").lower(), False)

    curserver = server(servername, username, password, server_url, enabled, jukebox)
    state.all_servers.append(curserver)
    if enabled:
        sys.stdout.write("Initializing server " + curserver.servername + ": ")
        sys.stdout.flush()
        curserver.goOnline()
        if curserver.online:
            state.server.append(curserver)

def iterServers():
    """A generator that goes through the active servers"""
    for one_server in state.server:
        print "On server: " + one_server.servername
        yield one_server

def parseInput(command):
    """Parse the command line input"""

    arg = False

    # Parse the command
    if command.count(' ') > 0:
        arg = command[command.index(' ')+1:]
        command = command[:command.index(' ')]

    # Display how we parsed the command
    if options.verbose:
        print str(command)+":"+str(arg)

    # Interpret the command
    if command == "artist":
        for one_server in iterServers():
            one_server.library.searchArtists(arg)
    elif command == "album":
        for one_server in iterServers():
            one_server.library.searchAlbums(arg)
    elif command == "folder":
        for one_folder in iterServers():
            one_folder.library.searchFolders(arg)
    elif command == "song":
        for one_server in iterServers():
            one_server.library.searchSongs(arg)
    elif command == "update":
        for one_server in iterServers():
            one_server.library.updateLib()
    elif command == "rebuild":
        for one_server in iterServers():
            os.unlink(getHome(one_server.pickle))
            one_server.goOnline()
    elif command == "new":
        for one_server in iterServers():
            one_server.library.getSpecialAlbums(number=arg)
    elif command == "random":
        for one_server in iterServers():
            one_server.library.getSpecialAlbums(albtype='random',number=arg)
    elif command == "server":
        chooseServer(arg)
    elif command == "addserver":
        addServer()
    elif command == "now":
        nowPlaying()
    elif command == "silence":
        stopPlaying()
    elif command == "play":
        if arg:
            parseInput(arg)
        playPrevious(play=True)
    elif command == "queue":
        if arg:
            parseInput(arg)
        playPrevious()
    elif command == "live":
        live(arg)
    elif command == "write":
        writeMessage(arg)
    elif command == "read":
        getMessages()
    elif command == "help" or command == "h":
        print "Commands:"
        print "   'addserver' - interactively add a new server."
        print "   'artist' - display all artists."
        print "   'artist ID' - display albums of artist ID."
        print "   'artist query' - display albums of artists which contain 'query'."
        print "   'album ID' - displays songs in album ID."
        print "   'song ID' - display the song with the given ID."
        print "   'song query' - search all songs for query."
        print "   'play' - play results of previous search immediately."
        print "   'play artist|album|song query|ID' - play whatever the artist, album, or song query turns up immediately."
        print "   'queue' - queue results of previous search."
        print "   'queue artist|album|song query|ID' - queue whatever the artist, album, or song query turns up."
        print "   'now' - shows who is currently listening to what."
        print "   'new [numresults]' - prints new albums added to the server."
        print "   'write message' - Writes message to the subsonic chat."
        print "   'random [numresults]' - prints a random list of albums from the server."
        print "   'read' - Displays subsonic chat messages."
        print "   'silence' - stop anything that is currently playing."
        print "   'server' - switch active servers. Run with no args for help."
        print "   'quit', 'q', or ctrl-d - exit the CLI."
    elif command == "quit" or command == "q":
        gracefulExit()
    elif command == "":
        return
    else:
        print "Invalid command '" + command + "'. Type 'help' for help."


class folder:
    """This class implements the logical concept of a folder."""
    data_dict = None
    children = []
    songs = []

    def __init__(self, server=None, fold_id=None, data_dict=None):
        """Create a folder heirarchy. Recursively calls itself with fold_id set to build the tree."""
        self.children = []
        self.songs = []
        self.data_dict = data_dict
        self.server = server

        if fold_id:
            childrens = self.server.subRequest(page="getMusicDirectory ", list_type='child', extras={'id':fold_id})
            for child in childrens:
                if child.attrib['isDir'] == "true" and child.attrib['title'][-5:] != ".flac" and child.attrib['title'][-4:] != ".mp3":
                    print "Found directory: " + child.attrib['title'][0:getWidth(17)]
                    self.children.append(folder(server=self.server, fold_id=child.attrib['id'], data_dict=child.attrib))
                elif child.attrib['isDir'] == "true":
                    print "Skipping (subsonic bug): " + child.attrib['title'][0:getWidth(25)]
                else:
                    if child.attrib['id'] in self.server.library.song_ids:
                        self.songs.append(self.server.library.getSongById(child.attrib['id']))
                    else:
                        print "Found new song: " + child.attrib['title'][0:getWidth(16)]
                        self.songs.append(song(child.attrib, server=self.server))
        else:
            server.library.updateIDS()
            folders = self.server.subRequest(page="getIndexes", list_type='artist')
            for one_folder in folders:
                self.children.append(folder(server=self.server, fold_id=one_folder.attrib['id'], data_dict=one_folder.attrib))

    def playSTR(self):
        """Either return the needed playlist data, or run the command to add the song to the jukebox"""

        if self.server.jukebox:
            for child in self.children:
                child.playSTR()
            for one_song in self.songs:
                one_song.playSTR()
        else:
            playlist = ""
            for child in self.children:
                playlist += child.playSTR()
            for one_song in self.songs:
                playlist += one_song.playSTR()
            return playlist

    def updateServer(self, server):
        """Update the server this folder is linked to"""
        self.server = server
        for child in self.children:
            child.updateServer(server)
        for one_song in self.songs:
            one_song.updateServer(server)

    def recursivePrint(self, level=5, indentations=0):
        """Prints children up to level n"""
        if not self.data_dict is None:
            name_title = self.data_dict.get('title','?').encode('utf-8')[0:getWidth(6)]
            if name_title == "?":
                name_title = self.data_dict.get('name','?').encode('utf-8')[0:getWidth(6)]
            res = "%-4s: %s" % (self.data_dict['id'].encode('utf-8'), name_title)
            if indentations > 0:
                res = "   "*indentations + res
        else:
            res = "   "*indentations

        if level > 0:
            for child in self.children:
                res += "\n" + child.recursivePrint(level-1, indentations+1)
            for one_song in self.songs:
                res += "\n" + one_song.recursivePrint(level-1, indentations+1)
        return res

    def getSongs(self):
        """Get all of the songs that we can see"""
        song_list = []
        song_list.extend(self.songs)
        for child in self.children:
            song_list.extend(child.getSongs())
        return song_list

    def getFolders(self):
        folder_list = self.children[:]
        for child in self.children:
            folder_list.extend(child.getFolders())
        return folder_list

    # Implement expected methods
    def __iter__(self):
        return iter(self.children)
    def __len__(self):
        return len(self.children)
    def __str__(self):
        return self.recursivePrint(1)

class song:
    """This class implements the logical concept of a song."""
    data_dict = None

    def __init__(self, data_dict, server=None):
        """We need the dictionary to create a song."""
        self.server = server
        if data_dict:
            self.data_dict = data_dict
        else:
            raise ValueError('You must pass the song dictionary to create a song.')

    def updateServer(self, server):
        """Update the server this song is linked to"""
        self.server = server

    def playSTR(self):
        """If in jukebox mode, have subsonic add the song to the jukebox playlist. Otherwise return the playlist string"""
        if self.server.jukebox:
            self.server.subRequest(page="jukeboxControl", list_type='jukeboxStatus', extras={'action':'add', 'id':self.data_dict['id']})
        else:
            return "#EXTINF:" + self.data_dict.get('duration','?').encode('utf-8') + ',' + \
            self.data_dict.get('artist','?').encode('utf-8') + ' - ' + self.data_dict.get('title','?').encode('utf-8') +\
             "\n" + self.server.subRequest(page="stream", extras={'id':self.data_dict['id']}) + "\n"

    def __str__(self):
        return "%-3s: %s\n   %-4s: %s\n      %-5s: %s" % \
                (self.data_dict.get('artistId','?').encode('utf-8'), self.data_dict.get('artist','?').encode('utf-8')[0:getWidth(5)],\
                self.data_dict.get('albumId','?').encode('utf-8'), self.data_dict.get('album','?').encode('utf-8')[0:getWidth(9)],\
                self.data_dict.get('id','?').encode('utf-8'), self.data_dict.get('title','?').encode('utf-8')[0:getWidth(13)])

    def getDetails(self):
        """Print in a columnar mode that works well with multiple songs"""
        return "%-6s|%-5s|%-5s|%-20s|%-20s|%-19s" % (self.data_dict.get('id',"?"), self.data_dict.get('albumId',"?"), self.data_dict.get('artistId',"?"), self.data_dict.get('title',"?")[:20], self.data_dict.get('album',"?")[:20], self.data_dict.get('artist',"?")[:getWidth(61)])

    def recursivePrint(self, level=5, indentations=0):
        """Prints children up to level n"""
        res = "%-5s: %s" % (self.data_dict.get('id','?').encode('utf-8'), self.data_dict.get('title','?').encode('utf-8')[0:getWidth(7+3*indentations)])
        if indentations > 0:
            res = "   "*indentations + res
        return res


class album:
    """This class implements the logical concept of an album."""
    data_dict = None
    songs = []

    def __init__(self, data_dict, server=None):
        """We need the dictionary to create an album."""
        self.songs = []
        self.server = server
        if data_dict:
            self.data_dict = data_dict
            songs = self.server.subRequest(page="getAlbum", list_type='song', extras={'id':self.data_dict['id']})
            sys.stdout.write('.')
            sys.stdout.flush()
            for one_song in songs:
                self.songs.append(song(one_song.attrib, server=self.server))
            # Sort the songs by track number
            self.songs.sort(key=lambda k: int(k.data_dict.get('track','0')))
        else:
            raise ValueError('You must pass the album dictionary to create an album.')

    def updateServer(self, server):
        """Update the server this album is linked to"""
        self.server = server
        for one_song in self.songs:
            one_song.updateServer(server)

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
        res = "%-4s: %s" % (self.data_dict.get('id','?').encode('utf-8'), self.data_dict.get('name','?').encode('utf-8')[0:getWidth(6+3*indentations)])
        if indentations > 0:
            res = "   "*indentations + res
        if level > 0:
            for one_song in self.songs:
                res += "\n" + one_song.recursivePrint(level-1, indentations+1)
        return res

    def specialPrint(self):
        return "%-3s: %-20s %-3s: %-3s" % (self.data_dict.get('artistId','?').encode('utf-8'), self.data_dict.get('artist','?').encode('utf-8')[0:20], self.data_dict.get('id','?').encode('utf-8'), self.data_dict.get('name','?').encode('utf-8')[0:getWidth(31)])

    # Implement expected methods
    def __iter__(self):
        return iter(self.songs)
    def __len__(self):
        return len(self.songs)
    def __str__(self):
        return "%-3s: %s\n" % (self.data_dict.get('artistId','?').encode('utf-8'), self.data_dict.get('artist','?').encode('utf-8')[0:getWidth(5)]) + self.recursivePrint(1,1)


class artist:
    """This class implements the logical concept of an artist."""
    data_dict = None
    albums = []

    def addAlbums(self, albums):
        """Add any number of albums to the artist"""
        for one_album in albums:
            self.albums.append(album(one_album.attrib, server=self.server))

    def updateServer(self, server):
        """Update the server this artist is linked to"""
        self.server = server
        for one_album in self.albums:
            one_album.updateServer(server)

    def __init__(self, artist_id=None, server=None):
        """We need the dictionary to create an artist."""
        self.albums = []
        self.server = server

        if artist_id is not None:
            # Fetch the whole XML tree for this artist
            data_dict = self.server.subRequest(page="getArtist", list_type='album', extras={'id':artist_id}, retroot=True)

            if data_dict == "err":
                return None

            if len(data_dict) == 1:
                self.data_dict = data_dict[0].attrib
                self.addAlbums(data_dict[0].getchildren())
            else:
                print data_dict
                raise ValueError('The root you passed includes more than one artist.')
            # Sort the albums by ID
            self.albums.sort(key=lambda k: int(k.data_dict.get('id','0')))
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
        res = "%-3s: %s" % (self.data_dict.get('id','?').encode('utf-8'), self.data_dict.get('name','?').encode('utf-8')[0:getWidth(5+3*indentations)])
        if indentations > 0:
            res = "   "*indentations + res
        if level > 0:
            for one_album in self.albums:
                res += "\n" + one_album.recursivePrint(level-1, indentations+1)
        return res

    # Implement expected methods
    def __iter__(self):
        return iter(self.albums)
    def __len__(self):
        return len(self.albums)
    def __str__(self):
        return self.recursivePrint(0)


class library:
    """This class implements the logical concept of a library."""
    artists = []
    initialized = False

    def __init__(self, server=None):
        if server is None:
            raise ValueError("You must specify a corresponding server for this library.")
        self.artists = []
        self.server = server
        self.folder = None

    def updateServer(self, server):
        """Update the server this library is linked to"""
        self.server = server
        for one_artist in self.artists:
            one_artist.updateServer(server)
        for one_folder in self.folder.getFolders():
            one_folder.updateServer(server)

    def addArtist(self, artist_id):
        """Add an artist to the library"""
        new_artist = artist(artist_id, server=self.server)
        if new_artist:
            self.artists.append(new_artist)

    def updateIDS(self):
        """Calculate a list of all song, album, and artist ids"""
        self.album_ids = map(lambda x:x.data_dict['id'], self.getAlbums())
        self.artist_ids = map(lambda x:x.data_dict['id'], self.getArtists())
        self.song_ids = map(lambda x:x.data_dict['id'], self.getSongs())

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
            if one_song.data_dict['id'] == song_id:
                self.prev_res = [one_song]
                return one_song
        self.prev_res = []
        return None

    def getArtistById(self, artist_id):
        """Return an artist based on ID"""
        for one_artist in self.getArtists():
            if one_artist.data_dict['id'] == artist_id:
                return one_artist
        return None

    def getAlbumById(self, album_id):
        """Return an artist based on ID"""
        for one_album in self.getAlbums():
            if one_album.data_dict['id'] == album_id:
                return one_album
        return None

    def searchSongs(self, search=None):
        """Search through song names or ids for the query"""
        if search:
            res = []
            for one_song in self.getSongs():
                if search.isdigit():
                    if one_song.data_dict['id'] == search:
                        res.append(one_song)
                else:
                    if search.lower() in one_song.data_dict['title'].lower():
                        res.append(one_song)
        else:
            res = self.getSongs()

        self.prev_res = res


        # If they want all songs, only print the song names
        if not search:
            for one_song in res:
                print one_song.recursivePrint(0,0)

        # There is a query
        if search:
            if len(res) == 0:
                print "No songs matched your query."
                return
            if getWidth() >= 80:
                print "%-6s %-5s %-5s %-20s %-20s %-19s" % ("SongID", "AlbID", "ArtID", "Song", "Album", "Artist")
                for one_song in res:
                    print one_song.getDetails()
            else:
                print "For optimal song display, please resize terminal to be at least 80 characters wide."
                for one_song in res:
                    print one_song

    def searchAlbums(self, search=None):
        """Search through albums names or ids for the query"""
        if search:
            res = []
            for one_album in self.getAlbums():
                if search.isdigit():
                    if one_album.data_dict['id'] == search:
                        res.append(one_album)
                else:
                    if search.lower() in one_album.data_dict['name'].lower():
                        res.append(one_album)
        else:
            res = self.getAlbums()

        self.prev_res = res

        # Print the results
        if len(res) == 0:
            print "No albums matched your query."
            return
        for one_album in res:
            if search:
                print one_album
            else:
                print one_album.recursivePrint(0)

    def searchArtists(self, search=None):
        """Search through artists names or ids for the query"""
        if search:
            res = []

            for one_artist in self.getArtists():
                if search.isdigit():
                    if one_artist.data_dict['id'] == search:
                        res.append(one_artist)
                else:
                    if search.lower() in one_artist.data_dict['name'].lower():
                        res.append(one_artist)
        else:
            res = self.getArtists()

        self.prev_res = res

        # Print the results
        if len(res) == 0:
            print "No artists matched your query."
            return
        for one_artist in res:
            if search:
                print one_artist.recursivePrint(1)
            else:
                print one_artist.recursivePrint(0)

    def searchFolders(self, search=None):
        """ Search through the folders for the query or id"""
        if not hasattr(self, 'folder') or self.folder is None:
            print "Building folder..."
            self.folder = folder(server=self.server)
            # Pickle the new library
            pickleLibrary(self.server)

        res = []
        if search:

            for one_folder in self.folder.getFolders():
                if search.isdigit():
                    if one_folder.data_dict['id'] == search:
                        res.append(one_folder)
                else:
                    tn = one_folder.data_dict.get('title','?').lower()
                    if tn == "?":
                        tn = one_folder.data_dict.get('name','?').lower()
                    if search.lower() in tn:
                        res.append(one_folder)
        else:
            res = self.folder.children

        self.prev_res = res

        for one_folder in res:
            if search:
                print one_folder.recursivePrint(1)
            else:
                print one_folder.recursivePrint(0)

    def getSpecialAlbums(self, albtype='newest', number=10):
        """Returns either new or random albums"""

        # Process the supplied number
        if not number or not number.isdigit():
            number = 10
        else:
            number = int(number)

        if albtype == 'random':
            albums = self.getAlbums()
            if len(albums) < number:
                number = len(albums)
            res = random.sample(albums,number)
        elif albtype == 'newest':
            res = reversed(sorted(self.getAlbums(), key=lambda k:k.data_dict.get('created','?'))[-number:])
        else:
            raise ValueError("Invalid type to search for.")

        self.prev_res = res
        for item in self.prev_res:
            print item.specialPrint()

    # Implement expected methods
    def __iter__(self):
        return iter(self.artists)
    def __len__(self):
        return len(self.artists)
    def __str__(self):
        return self.recursivePrint(1,-1)


class server:
    """This class represents a server. It stores the password and makes queries."""

    def __init__(self, servername, username, password, server_url, enabled=True, jukebox=False):
        """A server object"""

        # Build the default parameters into a reusable hash
        self.default_params = {
          'u': username,
          'v': "1.9.0",
          'p': "enc:" + password.encode("hex"),
          'c': "subsonic-cli",
          'f': "xml"
        }

        if password == "":
            self.securepass = True
            self.default_params['p'] = ""
        else:
            self.securepass = False

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
        """Return a string corresponding the the config file format for this server"""
        password = self.default_params['p']
        if self.securepass:
            password = ""
        return "[%s]\nHost: %s\nUsername: %s\nPassword: %s\nJukebox: %s\nEnabled: %s\n\n" % (self.servername, self.server_url, self.default_params['u'], \
                password, str(self.jukebox), str(self.enabled))

    def __str__(self):
        return self.printConfig()

    def subRequest(self, page="ping", list_type='subsonic-response', extras={}, timeout=10, retroot=False):
        """Query subsonic, parse resulting xml and return an ElementTree"""

        # Add request specific parameters to our hash
        params = self.default_params.copy()
        params.update(extras)

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

        if self.default_params['p'] == "":
            password = getpass.getpass()
            self.default_params['p'] = "enc:" + password.encode("hex")

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
            self.library = library(self)
            sys.stdout.write("Building library.")
            self.library.fillArtists()
            pickleLibrary(self)
            print ""
        # Update the server that the songs use
        self.library.updateServer(self)


########################################################################
#              Methods and classes above, code below                   #
########################################################################

# Specify some basic information about our command
parser = OptionParser(usage="usage: %prog",version="%prog 6.6.6",description="Enqueue songs from subsonic.")
parser.add_option("--verbose", action="store_true", dest="verbose", default=False, help="More than you'll ever want to know.")
#parser.add_option("--player", action="store", dest="player", default="/usr/bin/vlc", help="Location of media player to queue songs in.")

# Options, parse 'em
(options, cmd_input) = parser.parse_args()
options.player = "/usr/bin/vlc"

# Create a class to hold the current state
class state_obj(object):
    pass
state = state_obj()
state.server = []
state.all_servers = []

# Make sure the .pysonic folder exists
if not os.path.isdir(getHome()):
    os.makedirs(getHome())

# Parse the config file, load (or query) the server data
config = ConfigParser.ConfigParser()
config.read(getHome("config"))
for one_server in config.sections():

    curserver = server(one_server, config.get(one_server,'username'), config.get(one_server,'password'), config.get(one_server,'host'), enabled=config.getboolean(one_server, 'enabled'), jukebox=config.getboolean(one_server, 'jukebox'))
    state.all_servers.append(curserver)

    if curserver.enabled:
        sys.stdout.write("Loading server " + curserver.servername + ": ")
        sys.stdout.flush()
        curserver.goOnline()
    else:
        print "Loading server " + curserver.servername + ": Disabled."

# Create our backup list of servers
for one_server in state.all_servers:
    if one_server.enabled and one_server.online:
        state.server.append(one_server)

# No valid servers
if len(state.server) < 1:
    if len(config.sections()) > 0:
        print "No connections established. Do you have at least one server specified in ~/.pysonic/config and are your username, server URL, and password correct?"
        sys.exit(10)
    else:
        print "No configuration file found. Configure a server now."
        addServer()

# If we made it here then it must be!
print "Successfully connected. Entering command mode:"

# Load previous command history
try:
    readline.read_history_file(getHome("history"))
except:
    pass

# Execute piped-in commands if there are any
mode = os.fstat(0).st_mode
if stat.S_ISFIFO(mode) or stat.S_ISREG(mode):
    for line in sys.stdin.readlines():
        parseInput(line.rstrip())
    sys.exit(0)

# Enter our loop, let them issue commands!
while True:
    # Catch control-c
    try:
        # Accept the input, quit on an EOF
        try:
            command = raw_input(":")
        except EOFError:
            gracefulExit()

        parseInput(command)

    except KeyboardInterrupt:
        print "\n\nWell aren't you impatient. Type 'q' or control-d to quit."

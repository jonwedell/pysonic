#!/usr/bin/env python3

"""
Jon Wedell

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

from __future__ import print_function

import os
import sys
import time
import stat
import string
import hashlib
import random
import signal
import socket
import getpass
import readline
import tempfile
import platform
import telnetlib
import subprocess
import xml.etree.ElementTree as ET
from optparse import OptionParser

# Determine if we are running in python3
PY3 = (sys.version_info[0] == 3)

# Python version dependent loads
#pylint: disable=wrong-import-order, ungrouped-imports
if PY3:
    import pickle
    import configparser
    from html.parser import HTMLParser
    from urllib.parse import urlencode
    from urllib.request import urlopen
    from urllib.error import HTTPError, URLError
else:
    from urllib import urlencode
    from urllib2 import urlopen, HTTPError, URLError
    import cPickle as pickle
    from HTMLParser import HTMLParser
    import ConfigParser as configparser

from lyrics import get_lyrics as genius_lyrics

# Python version dependant redefines
if not PY3:
    input = raw_input

# Module level functions

def get_home(filename=None):
    """ Returns the .pysonic directory location (full path) and
    if filename is specified returns the .pysonic directory plus
    that filename. """

    home_dir = os.path.abspath(os.path.join(os.path.expanduser("~"),
                                            ".pysonic/"))

    if filename:
        return os.path.join(home_dir, filename)
    else:
        return home_dir

def salt_generator(size=10, chars=string.ascii_uppercase + string.digits):
    """ Generates a random ASCII string (or string from whatever source
    you provide in chars) of length size. """

    return ''.join(random.SystemRandom().choice(chars) for _ in range(size))

def clean_get(obj, key):
    """ Returns a key with the song dictionary with the necessary
    changes made to properly display missing values and non-utf8
    results. """

    if PY3:
        return obj.data_dict.get(key, '?')
    else:
        return obj.data_dict.get(key, '?').encode('utf-8')

def get_lock(lockfile=None, killsignal=0):
    """ Opens a lock file to make sure that only one instance of
    pysonic is running at a time. """

    if lockfile is None:
        lockfile = get_home("lock")
    else:
        lockfile = get_home(lockfile)

    # If there is a lockfile, see if it is stale
    if os.path.isfile(lockfile):
        pid = open(lockfile, "r").read().strip()
        if not pid.isdigit():
            print("Corrupt PID in lock file (" +str(pid)+ "). Clearing.")
        else:
            pid = int(pid)
            try:
                os.kill(pid, killsignal)
            except OSError:
                print("Looks like pysonic quit abnormally last run.")
            else:
                if killsignal == 0:
                    print("It looks like pysonic is already running!")
                    return False
        os.unlink(lockfile)

    # Write our PID to the lockfile
    try:
        open(lockfile, "w").write(str(os.getpid()))
    except IOError:
        print("Could not write lockfile!")
        return False
    return True

def clear_lock(lockfile=None):
    """ Removes the pysonic lock file. """

    if lockfile is None:
        lockfile = get_home("lock")
    else:
        lockfile = get_home(lockfile)

    lockfile = get_home("lock")
    try:
        os.unlink(lockfile)
    except IOError:
        print("Could not unlink the lock file!")
        return False
    return True

def update_width(signal, frame):
    """ The terminal has resized, so figure out the new size."""

    # Check if we are outputting to a terminal style device
    mode = os.fstat(0).st_mode
    if stat.S_ISFIFO(mode) or stat.S_ISREG(mode):
        state['cols'] = 10000
    else:
        state['cols'] = os.popen('stty size', 'r').read().split()[1]

def get_width(used=0):
    """Get the remaining width of the terminal. """

    # Return the remaining terminal width
    return int(state['cols']) - used

def print_messages():
    """Get chat messages. """

    for one_server in state['server']:
        print("On server: " + one_server.server_name)
        messages = one_server.sub_request(page="getChatMessages",
                                          list_type='chatMessage')
        # Convert time from unix time to readable time
        for message in messages:
            mtime = time.ctime(float(message.attrib['time'])/1000).rstrip()
            message.attrib['time'] = mtime
            print("   At %s %s wrote %s." %
                  (message.attrib.get('time', '?'),
                   message.attrib.get('username', '?'),
                   message.attrib.get('message', '?')))

def write_message(message):
    """Write a chat message. """

    for one_server in state['server']:
        print("On server: " + one_server.server_name)
        messages = one_server.sub_request(page="addChatMessage",
                                          list_type='subsonic-response',
                                          extras={'message':message})
        if messages[0].attrib['status'] == 'ok':
            print("   Successfully wrote message: '" + str(message) + "'")

def get_similar(arg):
    """ Get a list of similar songs or similar artists. """

    # Get similar songs to now playing
    if not arg or arg.isdigit():
        if str(arg).isdigit():
            arg = int(arg)
        else:
            arg = 10
        playing_song = get_now_playing()
        if playing_song is None:
            print("Nothing is playing.")
            return
        similar_id = playing_song.data_dict['id']
        playing_song.server.library.get_similar_songs(similar_id, arg)
        return

    split_args = str(arg).split()
    if split_args[0] == "song":
        if len(split_args) == 1:
            print("Please specify the ID of a song to find similar songs for.")
            return
        for one_server in iter_servers():
            one_server.library.get_similar_songs(*split_args[1:])
    elif split_args[0] == "artist":
        print("Not yet implemented.")
    else:
        print("Please specify 'song', 'artist', or a number of similar songs "
              "to the now playing song to return.")

def get_now_playing():
    """ Returns the song that is currently playing. """

    stream_info = state['vlc'].read_write("status")

    try:
        stream_start = stream_info.index("?") + 1
    except ValueError:
        return None

    stream_end = stream_info.index(")")
    stream_info = stream_info[stream_start:stream_end].split("&")
    stream_dict = {}
    for item in stream_info:
        key, value = item.split("=")
        stream_dict[key] = value.strip()

    stream_id = int(stream_dict['sid'])
    song_id = int(stream_dict['id'])

    return state['all_servers'][stream_id].library.get_song_by_id(song_id)

def now_playing():
    """Get the now playing lists. """

    for one_server in state['server']:
        print("On server: " + one_server.server_name)
        playing = one_server.sub_request(page="getNowPlaying",
                                         list_type='entry')
        for one_person in playing:
            print("   %s minutes ago %s played %s by %s (ID:%s)" % (
                one_person.attrib.get('minutesAgo', '?'),
                one_person.attrib.get('username', '?'),
                one_person.attrib.get('title', '?'),
                one_person.attrib.get('artist', '?'),
                one_person.attrib.get('id', '?')))
            one_server.library.get_song_by_id(one_person.attrib['id'])

def choose_server(query=None):
    """Choose whether to display one server or all servers. """

    if query == "all":
        state['server'] = []
        for one_server in state['all_servers']:
            if not one_server.enabled:
                one_server.enabled = True
            if not one_server.online:
                one_server.go_online()
            if one_server.online:
                state['server'].append(one_server)
        print("Using server(s): %s" %
              ",".join([x.server_name for x in state['server']]))
    elif query:
        queries = set(query.replace(",", " ").split())
        myres = []
        serv_hash = {}
        for one_server in state['all_servers']:
            serv_hash[one_server.server_name] = one_server
        for query in queries:
            if query in serv_hash:
                one_server = serv_hash[query]
                if not one_server.enabled:
                    one_server.enabled = True
                if not one_server.online:
                    one_server.go_online()
                if one_server.online:
                    myres.append(one_server)
                    print("Selected server " + query + ".")
            else:
                print("No matching server (" + query +
                      ")! Choose from: " +
                      ",".join([x.server_name for x in state['all_servers']]))
        if len(myres) > 0:
            state['server'] = myres
        else:
            print("No servers matched your results.")
        print("Using server(s): %s" %
              ",".join([x.server_name for x in state['server']]))
        # Make sure that only enabled servers are enabled
        for one_server in state['all_servers']:
            one_server.enabled = False
        for one_server in state['server']:
            one_server.enabled = True
    else:
        if len(state['server']) == len(state['all_servers']):
            print("All servers enabled. Enter a server name to choose that "
                  "server.")
            print("Choose from: %s" %
                  ",".join([x.server_name for x in state['all_servers']]))
        else:
            print("Currently active servers: %s" %
                  ",".join([x.server_name for x in state['server']]))
            print("All known servers: %s" %
                  ",".join([x.server_name for x in state['all_servers']]))
            print("Type 'server all' to restore all servers, or enter server"
                  " names to select.")

def print_previous():
    """Print off whatever the saved result is. """

    for one_server in iter_servers():
        if (not one_server.library.prev_res or
                len(one_server.library.prev_res) == 0):
            print("No saved result.")
        else:
            for item in one_server.library.prev_res:
                print(item.recursive_print(level=1, indentations=0))

def follow_lyrics():
    """ Watches the now playing song, and when it changes it prints the
    lyrics. """

    # Get the playing song
    cur_song = get_now_playing()

    try:
        # Loop while there is a real song
        while cur_song:
            # Print the lyrics now
            os.system("reset")
            print(cur_song.get_lyrics())

            # Check if the song has changed once a second
            new_song = get_now_playing()
            while new_song == cur_song:
                time.sleep(1)
                new_song = get_now_playing()
            cur_song = new_song

    # Make sure that on control-c we return to the normal prompt
    except KeyboardInterrupt:
        return

def print_lyrics(arg):
    """ Prints the lyrics of the current song or a song specified by
    ID. """

    # Get the lyrics of a song by ID
    if arg:
        if arg.isdigit():
            for one_server in iter_servers():
                the_song = one_server.library.get_song_by_id(arg)
                if the_song:
                    print(the_song.get_lyrics())
                else:
                    print("No results.")
        else:
            print("Lyrics search only supported for currently playing song or"
                  " by specifying song ID.")

    # Get the lyrics of the currently playing song
    else:
        playing_song = get_now_playing()
        if playing_song:
            print(get_now_playing().get_lyrics())
        else:
            print("Nothing is playing.")

def play_previous(play=False):
    """Play whatever the previous result was. """

    # Count the number of results
    results = 0

    # Get the play string
    playlist = ""
    for one_server in state['server']:
        res = one_server.library.play_string()
        results += res[1]
        playlist += res[0]

    # Make sure there is something to play
    if results == 0:
        print("Last command did not result in anything playable.")
        return

    # Create the m3u file
    rel_time = str(time.time())[-10:-3]
    playlist_file = os.path.join(tempfile.gettempdir(), rel_time + ".m3u")
    playlistf = open(playlist_file, "w")
    playlistf.write("#EXTM3U\n")
    playlistf.write(playlist)
    playlistf.close()

    if play:
        state['vlc'].write("clear")
        state['vlc'].write("enqueue " + playlist_file)
    else:
        state['vlc'].write("enqueue " + playlist_file)
    time.sleep(.1)
    state['vlc'].write("play")

def live():
    """Enter interactive python terminal. """

    import code
    vars = globals()
    vars.update(locals())
    shell = code.InteractiveConsole(vars)
    shell.interact()

def pickle_library(cur_server):
    """ Pickles the song library and writes it to disk. """

    # Don't save useless information in the pickle
    cur_server.library.update_server(None)
    cur_server.library.album_ids = None
    cur_server.library.artist_ids = None
    cur_server.library.song_ids = None
    cur_server.library.prev_res = None

    # Dump the pickle
    pickle.dump(cur_server.library, open(get_home(".tmp.pickle"), "wb"), 2)
    os.rename(get_home(".tmp.pickle"), cur_server.pickle)

    # Re-set the server
    cur_server.library.update_server(cur_server)

def graceful_exit(code=0):
    """Quit gracefully, saving state. """

    print("\nShutting down...")

    # Create the history file if it doesn't exist
    if not os.path.isfile(get_home("history")):
        open(get_home("history"), "a").close()
    readline.write_history_file(get_home("history"))

    # Write the current servers to the config file
    config_str = ""
    for one_server in state['all_servers']:
        config_str += one_server.print_config()
    open(get_home("config"), 'w').write(config_str)

    clear_lock()

    print("Goodbye!")
    sys.exit(code)


def add_server():
    """Interactively add a new server. """

    user_input_maps = {'y':True, 'yes':True, 't':True, 'true':True, 'n':False,
                       'no':True, 'f':False, 'false':False}

    server_name = ''.join(input("Informal name (one word is best):"
                                " ").split())
    server_url = input("URL or subsonic username: ")
    user_name = input("Username: ")
    print("Press enter to use secure password mode. (Prompt for password "
          "each start.)")
    password = getpass.getpass()
    bitrate = input("Max bitrate (enter 0 to stream raw or press enter to "
                    "use default value): ")
    enabled = user_input_maps.get(input("Enabled (y/n): ").lower(), True)
    jukebox = user_input_maps.get(input("Jukebox mode (y/n): ").lower(),
                                  False)
    scrobble = user_input_maps.get(input("Scrobble (y/n): ").lower(), False)

    curserver = SubServer(len(state['all_servers']), server_name, user_name,
                          password, server_url, enabled, bitrate, jukebox,
                          scrobble)
    state['all_servers'].append(curserver)
    if enabled:
        sys.stdout.write("Initializing server " + curserver.server_name + ": ")
        sys.stdout.flush()
        curserver.go_online()
        if curserver.online:
            state['server'].append(curserver)

def iter_servers():
    """A generator that goes through the active servers. """

    show_cur_server = False
    if len(state['server']) > 1:
        show_cur_server = True

    for one_server in state['server']:
        if show_cur_server:
            print("On server: " + one_server.server_name)
        yield one_server

def print_song_list(song_list):
    """ Nicely formats and prints a list of songs. """

    if len(song_list) == 0:
        print("No songs matched your query.")
        return
    if get_width() >= 80:
        print("%-6s %-5s %-5s %-20s %-20s %-19s" % ("SongID", "AlbID",
                                                    "ArtID", "Song",
                                                    "Album", "Artist"))
        for one_song in song_list:
            print(one_song.get_details())
    else:
        print("For optimal song display, please resize terminal to be at"
              " least 80 characters wide.")
        for one_song in song_list:
            print(one_song)

def parse_input(command):
    """Parse the command line input. """

    command = command.strip()
    multiple = command.split(";")
    if len(multiple) > 1:
        for com in multiple:
            parse_input(com)
        return

    arg = False

    # Parse the command
    if command.count(' ') > 0:
        arg = command[command.index(' ')+1:]
        command = command[:command.index(' ')]

    # Display how we parsed the command
    if options.verbose:
        print(str(command)+":"+str(arg))

    # Interpret the command
    if command == "artist":
        for one_server in iter_servers():
            one_server.library.search_artists(arg)
    elif command == "album":
        for one_server in iter_servers():
            one_server.library.search_albums(arg)
    elif command == "folder":
        for one_folder in iter_servers():
            one_folder.library.search_folders(arg)
    elif command == "song":
        for one_server in iter_servers():
            one_server.library.search_songs(arg)
    elif command == "rebuild":
        for one_server in iter_servers():
            os.unlink(get_home(one_server.pickle))
            one_server.library.initialized = False
            one_server.go_online()
    elif command == "new":
        for one_server in iter_servers():
            one_server.library.get_special_albums(number=arg)
    elif command == "rand" or command == "random":
        for one_server in iter_servers():
            one_server.library.get_special_albums(albtype='random', number=arg)
    elif command == "similar":
        get_similar(arg)
    elif command == "server":
        choose_server(arg)
    elif command == "addserver":
        add_server()
    elif command == "now":
        now_playing()
    elif command == "pause":
        state['vlc'].write("pause")
    elif command == "resume":
        state['vlc'].write("play")
    elif command == "next":
        state['vlc'].write("next")
        print(get_now_playing())
    elif command == "playlist":
        print(state['vlc'].read_write("playlist"))
    elif command == "prev":
        state['vlc'].write("prev")
        print(get_now_playing())
    elif command == "clear":
        state['vlc'].write("clear")
    elif command == "playing":
        print(get_now_playing())
    elif command == "vlc":
        print("Entering VLC shell:")
        sys.stdout.write(":")
        sys.stdout.flush()
        state['vlc'].telnet_con.interact()
        print("\nReturned to pysonic shell:")
    elif command == "goto":
        state['vlc'].write("goto " + arg)
        res = state['vlc'].read()
        if res != "":
            print(res)
        else:
            print(get_now_playing())
    elif command == "play":
        if arg:
            parse_input(arg)
        play_previous(play=True)
    elif command == "queue":
        if arg:
            parse_input(arg)
        play_previous()
    elif command == "live":
        live()
    elif command == "result":
        print_previous()
    elif command == "lyrics":
        print_lyrics(arg)
    elif command == "booklet":
        follow_lyrics()
    elif command == "write":
        write_message(arg)
    elif command == "read":
        print_messages()
    elif command == "vlchelp":
        print(state['vlc'].read_write("help"))
    elif command == "help" or command == "h":
        print("""Admin/Subsonic:
   'addserver' - interactively add a new server.
   'read' - Displays subsonic chat messages.
   'write message' - Writes message to the subsonic chat.
   'now' - shows who is currently listening to what on subsonic.
   'server' - switch active servers. Run with no args for help.
   'vlc' - drop into a direct connection with the VLC CLI
   'live' - drop into a python shell
   'quit', 'q', 'exit', or ctrl-d - exit the CLI.
Querying and playing:
   'artist [ID|query]' - display artists matching ID or query.
   'album [ID|query]' - displays albums matching ID or query.
   'song [ID|query]' - display songs matching ID or query.
   'similar [song] [numresults] - displays a list of songs similar to
the specified song.
   'play [artist|album|song query|ID]' - play whatever the artist,
album, or song query turns up immediately. (Play previous result
if no arguments.)
   'queue [artist|album|song query|ID]' - queue whatever the artist,
album, or song query turns up. (Queue previous result if no arguments.)
   'result' - print whatever matched the previous query.
   'new [numresults]' - prints new albums added to the server.
   'rand [numresults]' - prints a random list of albums from the server.
   'lyrics [songID]' - print the lyrics of the currently playing song
or the song specified by songID.
Playlist management:
   'playlist' - display the current playlist
   'clear' - clear the playlist
   'goto ID' - go to item with ID in playlist
   'next/prev' - skip to the next or previous track
   'playing' - shows what is currently playing on the local machine.
   'pause/resume' - pause or play music
   'vlchelp' - display additional help on VLC commands.""")
    elif command == "quit" or command == "q" or command == "exit":
        print(" See ya!")
        graceful_exit()
    elif command == "":
        return
    else:
        # Try sending their command to VLC
        if arg:
            print(state['vlc'].read_write("%s %s" % (command, arg)))
        else:
            print(state['vlc'].read_write(command))

class VLCInterface(object):
    """Allows for interfacing (or creating and then interfacing)
    with local VLC instance. """

    def __init__(self):
        try:
            self.telnet_con = telnetlib.Telnet("localhost", 4212, 3)
        except socket.error:
            # Send all command output to dev/null
            null = open("/dev/null", "w")

            # Use the player they specify
            if options.player:
                vlc_command = [options.player]

            # Try to figure out where the player is
            else:
                vlc_command = ["/usr/bin/vlc"]

                # If MacOS version exists
                if os.path.isfile("/Applications/VLC.app/Contents/MacOS/VLC"):
                    vlc_command = ["/Applications/VLC.app/Contents/MacOS/VLC"]

            # Make sure we have a valid VLC location
            if not os.path.isfile(vlc_command[0]):
                raise IOError("Did not find VLC binary at location: %s" %
                              options.player)

            # Figure out the interactive argument
            if platform.system() == "Linux":
                vlc_command.append("-I")
            else:
                # Mac
                vlc_command.append("--intf")

            vlc_command.extend(["Telnet", "--telnet-password", "admin",
                                "--no-loop", "--http-reconnect"])

            vlc_process = subprocess.Popen(vlc_command, stderr=null,
                                           stdout=null)

            while vlc_process.poll() is None:
                # Try opening the connection again
                try:
                    self.telnet_con = telnetlib.Telnet("localhost", 4212)
                    break
                except socket.error:
                    time.sleep(.01)

            # The VLC process died or never opened
            else:
                print("Could not connect to launched VLC process.")
                graceful_exit()

        # Do the login dance
        self.write("admin\n")
        self.read()
        # Make the VLC prompt match
        self.write("set prompt :\n")
        self.read()

    def read(self):
        """Read from the VLC socket. """

        try:
            # Make sure if they send a message they wait a bit
            #  before receiving
            time.sleep(.1)
            mesg = self.telnet_con.read_very_eager()
            read = mesg
            while len(read) > 0:
                read = self.telnet_con.read_very_eager()
                mesg += read
            if len(mesg) >= 3:
                mesg = mesg[:-3]
            elif len(mesg) == 1 and mesg == ":":
                mesg = ""
            return mesg.decode('utf-8')
        except (EOFError, socket.error):
            print("VLC socket died, please restart.")
            graceful_exit()

    def write(self, message):
        """Write a command to the VLC socket. """

        try:
            if message[-1:] != "\n":
                message += "\n"
            self.telnet_con.write(message.encode('ascii'))
        except (EOFError, socket.error):
            print("VLC socket died, please restart.")
            graceful_exit()

    def read_write(self, message):
        """Write a command and send back the response. """

        self.read()
        self.write(str(message))
        return self.read()

class Folder(object):
    """This class implements the logical concept of a folder."""

    data_dict = None
    children = []
    songs = []

    def __init__(self, server=None, fold_id=None, data_dict=None):
        """Create a folder heirarchy. Recursively calls itself with
        fold_id set to build the tree. """

        self.children = []
        self.songs = []
        self.data_dict = data_dict
        self.server = server

        if fold_id:
            childrens = self.server.sub_request(page="getMusicDirectory ",
                                                list_type='child',
                                                extras={'id':fold_id})
            for child in childrens:
                if (child.attrib['isDir'] == "true" and
                        child.attrib['title'][-5:] != ".flac" and
                        child.attrib['title'][-4:] != ".mp3"):
                    print("Found directory: %s" %
                          child.attrib['title'][0:get_width(17)])
                    self.children.append(Folder(server=self.server,
                                                fold_id=child.attrib['id'],
                                                data_dict=child.attrib))

                elif child.attrib['isDir'] == "true":
                    print("Skipping (subsonic bug): %s" %
                          child.attrib['title'][0:get_width(25)])
                else:
                    if child.attrib['id'] in self.server.library.song_ids:
                        song_id = child.attrib['id']
                        song = self.server.library.get_song_by_id(song_id)
                        self.songs.append(song)
                    else:
                        print("Found new song: %s" %
                              child.attrib['title'][0:get_width(16)])
                        self.songs.append(Song(child.attrib,
                                               server=self.server))
        else:
            server.library.update_ids()
            folders = self.server.sub_request(page="getIndexes",
                                              list_type='artist')
            for one_folder in folders:
                self.children.append(Folder(server=self.server,
                                            fold_id=one_folder.attrib['id'],
                                            data_dict=one_folder.attrib))

    def play_string(self):
        """Either return the needed playlist data, or run the command
        to add the song to the jukebox. """

        if self.server.jukebox:
            for child in self.children:
                child.play_string()
            for one_song in self.songs:
                one_song.play_string()
        else:
            playlist = ""
            for child in self.children:
                playlist += child.play_string()
            for one_song in self.songs:
                playlist += one_song.play_string()
            return playlist

    def update_server(self, server):
        """Update the server this folder is linked to. """

        self.server = server
        for child in self.children:
            child.update_server(server)
        for one_song in self.songs:
            one_song.update_server(server)

    def recursive_print(self, level=5, indentations=0):
        """Prints children up to level n. """

        if self.data_dict is not None:
            name_title = clean_get(self, 'title')
            name_title = name_title[0:get_width(6)]
            if name_title == "?":
                name_title = clean_get(self, 'name')
                name_title = name_title[0:get_width(6)]
            res = "%-4s: %s" % (clean_get(self, 'id'), name_title)
            if indentations > 0:
                res = "   "*indentations + res
        else:
            res = "   "*indentations

        if level > 0:
            for child in self.children:
                res += "\n" + child.recursive_print(level-1, indentations+1)
            for one_song in self.songs:
                res += "\n" + one_song.recursive_print(level-1, indentations+1)
        return res

    def get_songs(self):
        """Get all of the songs that we can see. """

        song_list = []
        song_list.extend(self.songs)
        for child in self.children:
            song_list.extend(child.get_songs())
        return song_list

    def get_folders(self):
        """ Get any subfolders from this folder. """

        folder_list = []
        for child in self.children:
            if child is not None:
                folder_list.append(child)
                folder_list.extend(child.get_folders())
        return folder_list

    # Implement expected methods
    def __iter__(self):
        return iter(self.children)
    def __len__(self):
        return len(self.children)
    def __str__(self):
        return self.recursive_print(1)

class Song(object):
    """This class implements the logical concept of a song. """

    data_dict = None

    def __init__(self, data_dict, server=None):
        """We need the dictionary to create a song. """

        self.server = server
        if data_dict:
            self.data_dict = data_dict
        else:
            raise ValueError('You must pass the song dictionary to create a '
                             'song.')

    def update_server(self, server):
        """Update the server this song is linked to. """

        self.server = server

    def play_string(self):
        """If in jukebox mode, have subsonic add the song to the jukebox
        playlist. Otherwise return the playlist string. """

        if self.server.jukebox:
            self.server.sub_request(page="jukeboxControl",
                                    list_type='jukeboxStatus',
                                    extras={'action':'add',
                                            'id':self.data_dict['id']
                                           })
        else:
            extras_dict = {'id':self.data_dict['id']}
            if self.server.bitrate == 0:
                extras_dict['format'] = "raw"
            elif self.server.bitrate is not None:
                extras_dict['maxBitRate'] = self.server.bitrate

            if self.server.scrobble:
                library = self.server.library
                scrobble_str = "#EXTINF:0,LastFM - This scrobbles %s\n%s" % (
                    clean_get(self, 'title'),
                    library.get_scrobble_url(clean_get(self, 'id')))
            else:
                scrobble_str = ""

            return "#EXTINF:%s,%s - %s\n%s\n%s\n" % (\
                    clean_get(self, 'duration'),
                    clean_get(self, 'artist'),
                    clean_get(self, 'title'),
                    self.server.sub_request(page="stream", extras=extras_dict),
                    scrobble_str)

    def __str__(self):
        return "%-3s: %s\n   %-4s: %s\n      %-5s: %s" % \
                (clean_get(self, 'artistId'),
                 clean_get(self, 'artist')[0:get_width(5)],
                 clean_get(self, 'albumId'),
                 clean_get(self, 'album')[0:get_width(9)],
                 clean_get(self, 'id'),
                 clean_get(self, 'title')[0:get_width(13)])

    def get_details(self):
        """Print in a columnar mode that works well with multiple songs. """

        return "%-6s|%-5s|%-5s|%-20s|%-20s|%-19s" % (\
                clean_get(self, 'id'),
                clean_get(self, 'albumId'),
                clean_get(self, 'artistId'),
                clean_get(self, 'title')[:20],
                clean_get(self, 'album')[:20],
                clean_get(self, 'artist')[:get_width(61)])

    def get_lyrics(self):
        """ Returns the lyrics of the song as a string as provided by
        the subsonic server. """

        try:
            artist, title, lyrics = genius_lyrics(clean_get(self, 'title'),
                                                  clean_get(self, 'artist'))
        except Exception as e:
            return "Error when fetching lyrics: %s" % str(e)

        if lyrics:
            return "%s | %s\n%s\n%s" % (artist, title, "-"*get_width(),
                                        lyrics)
        else:
            return "No lyrics available."

    def recursive_print(self, indentations=0, dummy_level=0):
        """Prints children up to level n. """

        max_len = get_width(7+3*indentations)
        res = "%-5s: %s" % (clean_get(self, 'id'),
                            clean_get(self, 'title')[0:max_len])
        if indentations > 0:
            res = "   "*indentations + res
        return res

class Album(object):
    """This class implements the logical concept of an album. """

    data_dict = None
    songs = []

    def __init__(self, data_dict, server=None):
        """We need the dictionary to create an album. """

        self.songs = []
        self.server = server
        if data_dict:
            self.data_dict = data_dict
            songs = self.server.sub_request(page="getAlbum",
                                            list_type='song',
                                            extras={'id':self.data_dict['id']})
            if not server.library.initialized:
                sys.stdout.write('.')
                sys.stdout.flush()
            for one_song in songs:
                self.songs.append(Song(one_song.attrib, server=self.server))
            # Sort the songs by track number
            self.songs.sort(key=lambda k: int(k.data_dict.get('track', '0')))
        else:
            raise ValueError('You must pass the album dictionary to create an'
                             ' album.')

    def update_server(self, server):
        """Update the server this album is linked to. """
        self.server = server
        for one_song in self.songs:
            one_song.update_server(server)

    def play_string(self):
        """Either return the needed playlist data, or run the command to
        add the song to the jukebox. """

        if self.server.jukebox:
            for one_song in self.songs:
                one_song.play_string()
        else:
            playlist = ""
            for one_song in self.songs:
                playlist += one_song.play_string()
            return playlist

    def recursive_print(self, level=5, indentations=0):
        """Prints children up to level n. """

        album_name = clean_get(self, 'name')
        album_name = album_name[0:get_width(6+3*indentations)]
        res = "%-4s: %s" % (clean_get(self, 'id'), album_name)
        if indentations > 0:
            res = "   "*indentations + res
        if level > 0:
            for one_song in self.songs:
                res += "\n" + one_song.recursive_print(indentations+1)
        return res

    def special_print(self):
        """ Used to print albums in list rather than heirarchical format. """

        format_str = "%4s: %-20s %-3s: %-3s"
        return format_str % (clean_get(self, 'artistId'),
                             clean_get(self, 'artist')[0:20],
                             clean_get(self, 'id'),
                             clean_get(self, 'name')[0:get_width(35)])

    # Implement expected methods
    def __iter__(self):
        return iter(self.songs)
    def __len__(self):
        return len(self.songs)
    def __str__(self):
        return "%-3s: %s\n%s" % (clean_get(self, 'artistId'),
                                 clean_get(self, 'artist')[0:get_width(5)],
                                 self.recursive_print(1, 1))


class Artist(object):
    """This class implements the logical concept of an artist. """

    data_dict = None
    albums = []

    def add_albums(self, albums):
        """Add any number of albums to the artist. """

        for one_album in albums:
            self.albums.append(Album(one_album.attrib, server=self.server))

    def update_server(self, server):
        """Update the server this artist is linked to. """

        self.server = server
        for one_album in self.albums:
            one_album.update_server(server)

    def __init__(self, artist_id=None, server=None):
        """We need the dictionary to create an artist. """

        self.albums = []
        self.server = server

        if artist_id is not None:
            # Fetch the whole XML tree for this artist
            data_dict = self.server.sub_request(page="getArtist",
                                                list_type='album',
                                                extras={'id':artist_id},
                                                retroot=True)

            if data_dict == "err":
                return None

            if len(data_dict) == 1:
                self.data_dict = data_dict[0].attrib
                self.add_albums(data_dict[0].getchildren())
            else:
                print(data_dict)
                raise ValueError('The root you passed includes more than one'
                                 ' artist.')
            # Sort the albums by ID
            self.albums.sort(key=lambda k: int(k.data_dict.get('id', '0')))
        else:
            raise ValueError('You must pass the artist dictionary to create an'
                             ' artist.')

    def play_string(self):
        """Either return the needed playlist data, or run the command to
        add the song to the jukebox. """

        if self.server.jukebox:
            for one_album in self.albums:
                one_album.play_string()
        else:
            playlist = ""
            for one_album in self.albums:
                playlist += one_album.play_string()
            return playlist

    def recursive_print(self, level=3, indentations=0):
        """Prints children up to level n. """

        max_len = get_width(5+3*indentations)
        res = "%-3s: %s" % (clean_get(self, 'id'),
                            clean_get(self, 'name')[0:max_len])
        if indentations > 0:
            res = "   "*indentations + res
        if level > 0:
            for one_album in self.albums:
                res += "\n" + one_album.recursive_print(level-1, indentations+1)
        return res

    # Implement expected methods
    def __iter__(self):
        return iter(self.albums)
    def __len__(self):
        return len(self.albums)
    def __str__(self):
        return self.recursive_print(0)


class Library(object):
    """This class implements the logical concept of a library. """

    artists = []
    initialized = False

    def __init__(self, server=None):
        if server is None:
            raise ValueError("You must specify a corresponding server for this"
                             " library.")
        self.artists = []
        self.server = server
        self.folder = None
        self.artist_ids = None
        self.song_ids = None
        self.album_ids = None
        self.last_update = None
        self.prev_res = []

    def update_server(self, server):
        """Update the server this library is linked to. """
        self.server = server
        for one_artist in self.artists:
            one_artist.update_server(server)
        # TODO: Update folders also.

    def add_artist(self, artist_id):
        """Add an artist to the library. """

        new_artist = Artist(artist_id, server=self.server)
        if new_artist:
            self.artists.append(new_artist)
            return True
        else:
            return False

    def update_ids(self):
        """Calculate a list of all song, album, and artist ids. """

        self.album_ids = [x.data_dict['id'] for x in self.get_albums()]
        self.artist_ids = [x.data_dict['id'] for x in self.get_artists()]
        self.song_ids = [x.data_dict['id'] for x in self.get_songs()]

    def update_library(self):
        """Check for new albums and artists"""

        updates = 0

        self.update_ids()
        new_albums = self.server.sub_request(page="getAlbumList2",
                                             list_type='album',
                                             extras={'type':'newest',
                                                     'size':50
                                                    })

        for one_album in new_albums:
            if one_album.attrib['artistId'] not in self.artist_ids:
                if self.add_artist(one_album.attrib['artistId']):
                    self.update_ids()
            elif one_album.attrib['id'] not in self.album_ids:
                artist = self.get_artist_by_id(one_album.attrib['artistId'])
                artist.add_albums([one_album])
                self.update_ids()
                print(artist.recursive_print())
                updates += 1
        self.last_update = time.time()
        return updates

    def fill_artists(self):
        """Query the server for all the artists and albums. """

        for one_artist in self.server.sub_request(page="getArtists",
                                                  list_type='artist'):
            self.add_artist(one_artist.attrib['id'])
        self.initialized = True

    def play_string(self, mylist=None, jukebox=False):
        """Either return the needed playlist data, or run the command
        to add the song to the jukebox. """

        # Make sure they have something to play
        if not hasattr(self, 'prev_res') or not self.prev_res:
            return ("", 0)

        res_string = ""
        num_ret = 0

        if mylist:
            for item in mylist:
                res_string += item.play_string()
                num_ret += 1
            return (res_string, num_ret)
        else:
            for item in self.prev_res:
                res_string += item.play_string()
                num_ret += 1
            return (res_string, num_ret)

        if jukebox:
            playlist = ""
            for one_artist in self.artists:
                playlist += one_artist.play_string()
                num_ret += 1
            return (playlist, num_ret)
        else:
            for one_artist in self.artists:
                one_artist.play_string()

    def recursive_print(self, level=5, indentations=0):
        """Prints children up to level n. """

        res = ""
        if indentations > 0:
            res = "   "*indentations
        if level > 0:
            for one_artist in self.artists:
                res += "\n" + one_artist.recursive_print(level - 1,
                                                         indentations + 1)
        return res

    def get_similar_songs(self, song_id, count=10):
        """ Finds a list of similar songs. """

        try:
            song_id = int(song_id)
        except ValueError:
            print("You must provide a song ID and not a song name for the "
                  "similar query.")
            return

        similar = self.server.sub_request(page="getSimilarSongs",
                                          list_type="song",
                                          extras={'id':song_id, 'count':count})
        similar = [Song(x.attrib, self.server) for x in similar]
        self.prev_res = similar
        print_song_list(similar)

    def get_songs(self):
        """Return a list of all songs in the library. """

        ret_songs = []
        for one_artist in self:
            for one_album in one_artist:
                for one_song in one_album:
                    ret_songs.append(one_song)
        return ret_songs

    def get_albums(self):
        """Return a list of all albums in the library. """

        ret_albums = []
        for one_artist in self:
            for one_album in one_artist:
                ret_albums.append(one_album)
        return ret_albums

    def get_artists(self):
        """Return a list of all artists in the library. """

        return self.artists

    def get_scrobble_url(self, song_id):
        """ Returns the URL to fetch in order to scrobble a song. """

        server = self.server
        server.generate_md5_password()

        # Add request specific parameters to our hash
        params = server.default_params.copy()
        params.update({'id':song_id})

        # Encode our parameters and send the request
        params = urlencode(params)

        # Encode the URL
        url = server.server_url.rstrip() + "scrobble.view" + "?" + params

        return url

    def get_song_by_id(self, song_id):
        """Fetch a song from the library based on its ID. """
        for one_song in self.get_songs():
            if one_song.data_dict['id'] == str(song_id):
                self.prev_res = [one_song]
                return one_song
        self.prev_res = []
        return None

    def get_artist_by_id(self, artist_id):
        """Return an artist based on ID. """

        for one_artist in self.get_artists():
            if one_artist.data_dict['id'] == str(artist_id):
                return one_artist
        return None

    def get_album_by_id(self, album_id):
        """Return an album based on ID. """

        for one_album in self.get_albums():
            if one_album.data_dict['id'] == str(album_id):
                return one_album
        return None

    def search_songs(self, search=None, store_only=False):
        """Search through song names or ids for the query. """

        if search:
            res = []

            chunks = search.split(" ")
            # They are searching by one or more ID
            if all(x.isdigit() for x in chunks):
                for chunk in chunks:
                    for one_song in self.get_songs():
                        if one_song.data_dict['id'] == chunk:
                            res.append(one_song)
            else:
                for one_song in self.get_songs():
                    if search.lower() in one_song.data_dict['title'].lower():
                        res.append(one_song)
        else:
            res = self.get_songs()

        self.prev_res = res

        if store_only:
            return

        # If they want all songs, only print the song names
        if not search:
            for one_song in res:
                print(one_song.recursive_print(0))

        # There is a query
        else:
            print_song_list(res)

    def search_albums(self, search=None):
        """Search through albums names or ids for the query. """

        if search:
            res = []

            # See if they are adding multiple album by ID
            chunks = search.split(" ")
            if all(x.isdigit() for x in chunks):
                for chunk in chunks:
                    for one_album in self.get_albums():
                        if one_album.data_dict['id'] == chunk:
                            res.append(one_album)
            else:
                for one_album in self.get_albums():
                    if search.lower() in one_album.data_dict['name'].lower():
                        res.append(one_album)
        else:
            res = self.get_albums()

        self.prev_res = res

        # Print the results
        if len(res) == 0:
            print("No albums matched your query.")
            return
        for one_album in res:
            if search:
                print(one_album)
            else:
                print(one_album.recursive_print(0))

    def search_artists(self, search=None):
        """Search through artists names or ids for the query. """

        if search:
            res = []

            chunks = search.split(" ")
            # They are searching by one or more ID
            if all(x.isdigit() for x in chunks):
                for chunk in chunks:
                    for one_artist in self.get_artists():
                        if one_artist.data_dict['id'] == chunk:
                            res.append(one_artist)

            # They are searching by name
            else:
                for one_artist in self.get_artists():
                    if search.lower() in one_artist.data_dict['name'].lower():
                        res.append(one_artist)
        else:
            res = self.get_artists()

        self.prev_res = res

        # Print the results
        if len(res) == 0:
            print("No artists matched your query.")
            return
        for one_artist in res:
            if search:
                print(one_artist.recursive_print(1))
            else:
                print(one_artist.recursive_print(0))

    def search_folders(self, search=None):
        """ Search through the folders for the query or id. """

        if not hasattr(self, 'folder') or self.folder is None:
            print("Building folder...")
            self.folder = Folder(server=self.server)
            # Pickle the new library
            pickle_library(self.server)

        res = []
        if search:

            for one_folder in self.folder.get_folders():
                if search.isdigit():
                    if one_folder.data_dict['id'] == search:
                        res.append(one_folder)
                else:
                    title = one_folder.data_dict.get('title', '?').lower()
                    if title == "?":
                        title = one_folder.data_dict.get('name', '?').lower()
                    if search.lower() in title:
                        res.append(one_folder)
        else:
            res = self.folder.children

        self.prev_res = res

        for one_folder in res:
            if search:
                print(one_folder.recursive_print(1))
            else:
                print(one_folder.recursive_print(0))

    def get_special_albums(self, albtype='newest', number=10):
        """Returns either new or random albums. """

        # Process the supplied number
        if not number or not str(number).isdigit():
            number = 10
        else:
            number = int(number)

        if albtype == 'random':
            albums = self.get_albums()
            if len(albums) < number:
                number = len(albums)
            res = random.sample(albums, number)
        elif albtype == 'newest':
            key = lambda k: k.data_dict.get('created', '?')
            res = sorted(self.get_albums(), reverse=True, key=key)[:number]
        else:
            raise ValueError("Invalid type to search for.")

        self.prev_res = res
        for item in self.prev_res:
            print(item.special_print())

    # Implement expected methods
    def __iter__(self):
        return iter(self.artists)
    def __len__(self):
        return len(self.artists)
    def __str__(self):
        return self.recursive_print(1, -1)


class SubServer(object):
    """This class represents a server. It stores the password and makes
    queries. """

    def __init__(self, server_id, server_name, user_name, password, server_url,
                 enabled=True, bitrate=None, jukebox=False, scrobble=False):
        """A server object. """

        # Build the default parameters into a reusable hash
        self.default_params = {
            'u': user_name,
            'v': "1.13.0",
            'c': "subsonic-cli",
            'f': "xml",
            'sid': server_id
        }
        # The 'sid' is not actually used by the server. We put it there
        #  so that we can identify what server a given song ID is
        #    playing on from the VLC stream. This is needed in order
        #      to properly implement get_now_playing()

        if password == "":
            self.securepass = True
            self.password = password
        else:
            self.securepass = False

            # Store the password hex encoded on disk
            if password[0:4] != "enc:":
                self.password = "enc:" + password.encode("hex")
            else:
                self.password = password

        # Clean up the server address
        if server_url.count(".") == 0:
            server_url += ".subsonic.org"
        if server_url[0:7] != "http://" and server_url[0:8] != "https://":
            server_url = "http://" + server_url
        if server_url[-6:] != "/rest/":
            server_url = server_url + "/rest/"
        self.server_id = server_id
        self.server_url = server_url
        self.scrobble = scrobble
        self.jukebox = jukebox
        self.server_name = server_name
        self.enabled = enabled

        if bitrate == "":
            self.bitrate = None
        else:
            self.bitrate = int(bitrate)

        self.online = False
        self.pickle = get_home(self.server_name + ".pickle")
        self.library = Library(server=self)

    def generate_md5_password(self):
        """Creates a random salt and sets the md5(password+salt) and
        salt in the default args."""

        salt = salt_generator()
        self.default_params['s'] = salt

        if not PY3:
            to_hash = self.password[4:].decode("hex") + salt
            self.default_params['t'] = hashlib.md5(to_hash).hexdigest()
        else:
            pwd = bytes.fromhex(self.password[4:]).decode('utf-8')
            to_hash = "%s%s" % (pwd, salt)
            to_hash = to_hash.encode("ascii")
            self.default_params['t'] = hashlib.md5(to_hash).hexdigest()

    def print_config(self):
        """Return a string corresponding the the config file format
        for this server. """

        password = self.password
        if self.securepass:
            password = ""
        print_bitrate = str(self.bitrate)
        if self.bitrate is None:
            print_bitrate = ""
        conf = "[%s]\nHost: %s\nUsername: %s\nPassword: %s\nBitrate: %s\n"\
               "Jukebox: %s\nEnabled: %s\nScrobble: %s\n\n" % (
                   self.server_name, self.server_url, self.default_params['u'],
                   password, print_bitrate, str(self.jukebox),
                   str(self.enabled), str(self.scrobble))

        return conf

    def __str__(self):
        return self.print_config()

    def sub_request(self, page="ping", list_type='subsonic-response',
                    extras=None, timeout=10, retroot=False):
        """Query subsonic, parse resulting xml and return an ElementTree. """

        # Generate a unique salt for this request
        self.generate_md5_password()

        # Add request specific parameters to our hash
        params = self.default_params.copy()
        if extras is None:
            extras = {}
        params.update(extras)

        # Encode our parameters and send the request
        for key in list(params.keys()):
            try:
                params[key] = params[key].encode('utf-8')
            except AttributeError:
                pass
        params = urlencode(params)

        # Encode the URL
        tmp = self.server_url.rstrip() + page.rstrip() + "?" + params

        # To stream we only want the URL returned, not the data
        if page == "stream":
            return tmp

        if options.verbose:
            print(tmp)

        # Get the server response
        try:
            stringres = urlopen(tmp, timeout=timeout).read()
        except (socket.timeout, URLError):
            try:
                stringres = urlopen(tmp, timeout=timeout).read()
            except (socket.timeout, URLError):
                print("Request to subsonic server timed out twice.")
                graceful_exit()
        if PY3:
            stringres = stringres.decode("utf-8")

        # Parse the XML
        root = ET.fromstring(stringres)

        if options.verbose:
            print(stringres)
            print(root)

        # Make sure the result is valid
        if root.attrib['status'] != 'ok':
            raise ValueError("Server responded with error: %s" %
                             root[0].attrib['message'])

        # Short circuit return the whole tree if requested
        if retroot:
            return root

        # Return a list of the elements with the specified type
        return list(root.getiterator(tag='{http://subsonic.org/restapi}' +
                                     list_type))

    def go_online(self):
        """Ping the server to ensure it is online, if it is load the
        pickle or generate the local cache if necessary. """

        if self.password == "":
            self.password = "enc:" + getpass.getpass().encode("hex")

        sys.stdout.write("Checking if server " + self.server_name +
                         " is online: ")
        sys.stdout.flush()

        # Don't add the server to our server list if it crashes out
        try:
            self.sub_request(timeout=2)
        except (HTTPError, ValueError):
            self.online = False
            return

        self.online = True
        sys.stdout.write('Yes\n')
        sys.stdout.flush()

        # Try to load the pickle, build the library if neccessary
        need_new_build = False
        try:
            self.library = pickle.load(open(self.pickle, "rb"))
        except IOError:
            need_new_build = True
        except (EOFError, TypeError, AttributeError, pickle.UnpicklingError):
            print("Library archive corrupt or generated by old version of"
                  " pysonic. Rebuilding library.")
            need_new_build = True

        if need_new_build:
            self.library = Library(self)
            sys.stdout.write("Building library.")
            self.library.fill_artists()
            pickle_library(self)
            print("")

        # Update the server that the songs use
        self.library.update_server(self)
        # Update the library in the background
        if not options.stdin:
            if self.library.update_library() > 0:
                print("Saving new library.")
                pickle_library(self)

########################################################################
#              Methods and classes above, code below                   #
########################################################################

# Update terminal size when window is resized
signal.signal(signal.SIGWINCH, update_width)

# Specify some basic information about our command
parser = OptionParser(usage="usage: %prog", version="%prog .9",
                      description="Enqueue songs from subsonic.")

parser.add_option("--verbose", action="store_true", dest="verbose",
                  default=False, help="More than you'll ever want to know.")

parser.add_option("--passthrough", action="store_true", dest="passthrough",
                  default=False, help="Send commands directly to VLC without "
                                      "loading anything.")

parser.add_option("--vlc-location", action="store", dest="player",
                  default=None, help="Location of VLC binary.")

# Options, parse 'em
(options, cmd_input) = parser.parse_args()

if stat.S_ISFIFO(os.fstat(0).st_mode) or stat.S_ISREG(os.fstat(0).st_mode):
    options.stdin = True
    options.pingtime = False
else:
    options.stdin = False

# Use a dictionary to hold the state
state = {}
state['vlc'] = None
state['server'] = []
state['all_servers'] = []
state['cols'] = 80

# If they only want to send commands to VLC, go ahead
if options.passthrough:
    state['vlc'] = VLCInterface()
    if options.stdin:
        for line in sys.stdin.readlines():
            print(state['vlc'].read_write(line.rstrip()))
    else:
        print("Passthrough mode only works on piped-in commands.")
    sys.exit(0)

# Make sure the .pysonic folder exists
if not os.path.isdir(get_home()):
    os.makedirs(get_home())

# Get a lock (make sure we don't run twice at once)
if not get_lock():
    sys.exit(1)

# Parse the config file, load (or query) the server data
config = configparser.ConfigParser()
config.read(get_home("config"))
for each_server in config.sections():

    try:
        scrobble_plays = config.getboolean(each_server, 'scrobble')
    except configparser.NoOptionError:
        scrobble_plays = False

    new_server = SubServer(len(state['all_servers']), each_server,
                           config.get(each_server, 'username'),
                           config.get(each_server, 'password'),
                           config.get(each_server, 'host'),
                           enabled=config.getboolean(each_server, 'enabled'),
                           bitrate=config.get(each_server, 'bitrate'),
                           jukebox=config.getboolean(each_server, 'jukebox'),
                           scrobble=scrobble_plays)
    state['all_servers'].append(new_server)

    if new_server.enabled:
        sys.stdout.write("Loading server " + new_server.server_name + ": ")
        sys.stdout.flush()
        new_server.go_online()
    else:
        print("Loading server " + new_server.server_name + ": Disabled.")

# Create our list of active servers
for each_server in state['all_servers']:
    if each_server.enabled and each_server.online:
        state['server'].append(each_server)

# No valid servers
if len(state['server']) < 1:
    if len(config.sections()) > 0:
        print("No connections established. Do you have at least one server "
              "specified in ~/.pysonic/config and are your username, server "
              "URL, and password correct?")
        clear_lock()
        sys.exit(10)
    else:
        print("No configuration file found. Configure a server now.")
        add_server()

# Connect to the VLC interface
state['vlc'] = VLCInterface()

# If we made it here then it must be!
print("Successfully connected. Entering command mode:")

# Load previous command history
try:
    readline.read_history_file(get_home("history"))
except IOError:
    pass

# Execute piped-in commands if there are any
if options.stdin:
    for line in sys.stdin.readlines():
        parse_input(line.rstrip())
    clear_lock()
    sys.exit(0)

# First run any command line commands
for cmd in cmd_input:
    parse_input(cmd)

# Enter our loop, let them issue commands!
while True:

    # Catch control-c
    try:
        # Accept the input, quit on an EOF
        try:
            cmd = input(":")
        except EOFError:
            graceful_exit()

        parse_input(cmd)

    except KeyboardInterrupt:
        graceful_exit()


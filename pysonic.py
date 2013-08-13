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

import sys
import urllib
import urllib2
import xml.etree.ElementTree as ET
from optparse import OptionParser, OptionGroup
import readline
import tempfile
import os
import subprocess
import time
import cPickle as pickle
import ConfigParser

# Specify some basic information about our command
parser = OptionParser(usage="usage: %prog",version="%prog 6.6.6",description="Enqueue songs from subsonic.")
parser.add_option("--verbose", action="store_true", dest="verbose", default=False, help="More than you'll ever want to know.")
parser.add_option("--player", action="store", dest="player", default="/usr/bin/vlc", help="Location of media player to queue songs in.")

# Options, parse 'em
(options, cmd_input) = parser.parse_args()


def getWidth(used=0):
    """Get the remaining width of the terminal"""

    # Only update the width of the terminal every 5 seconds (otherwise we will fork a gazillion processes)
    if not hasattr(state, 'cols') or state.coltime + 5 < time.time():
        state.cols = os.popen('stty size', 'r').read().split()[1]
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
    p = subprocess.Popen(['killall', options.player], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
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
        queries = query.split()
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
    else:
        if len(state.server) == len(state.all_servers):
            print "All servers enabled. Enter a server name to choose that server."
            print "Choose from: " + str(",".join(map(lambda x:x.servername, state.all_servers)))
        else:
            print "Currently active servers: " + str(",".join(map(lambda x:x.servername, state.server)))
            print "All known servers: " + str(",".join(map(lambda x:x.servername, state.all_servers)))
            print "Specify 'all' to restore all servers, or enter server names to select."


# Play whatever the previous result was
def playPrevious(play=False):

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

# Enter python terminal
def live(arg=None):
    if arg:
        exec(arg)
    else:
        import code
        vars = globals().copy()
        vars.update(locals())
        shell = code.InteractiveConsole(vars)
        shell.interact()

# Quit gracefully
def gracefulExit():
    # Create the history file if it doesn't exist
    open(os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic","history")), "wa").close()
    readline.write_history_file(os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic","history")))
    config = ""
    for server in state.all_servers:
        config += server.printConfig()
    open(os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic", "config")), 'w').write(config)
    print " See ya!"
    sys.exit(0)

# Parse the input string
def parseInput(command):

    arg = False

    # Parse the command
    if command.count(' ') > 0:
        arg = command[command.index(' ')+1:]
        command = command[:command.index(' ')]

    # Display how we interpreted the command
    if options.verbose:
        print str(command)+":"+str(arg)

    # Interpret the command
    if command == "artist":
        for one_server in state.server:
            print "On server: " + one_server.servername
            for one_artist in one_server.library.searchArtists(arg):
                if arg:
                    print one_artist.recursivePrint(1)
                else:
                    print one_artist.recursivePrint(0)
    elif command == "album":
        for one_server in state.server:
            print "On server: " + one_server.servername
            for one_album in one_server.library.searchAlbums(arg):
                if arg:
                    print one_album
                else:
                    print one_album.recursivePrint(0)

    elif command == "song":
        for one_server in state.server:
            print "On server: " + one_server.servername
            for one_song in one_server.library.searchSongs(arg):
                if arg:
                    print one_song
                else:
                    print one_song.recursivePrint(0,0)
    elif command == "server":
        chooseServer(arg)
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
        print "   'write message' - Writes message to the subsonic chat."
        print "   'read' - Displays subsonic chat messages."
        print "   'silence' - stop anything that is currently playing."
        print "   'quit' or 'q' - exit the CLI."
    elif command == "quit" or command == "q":
        gracefulExit()
    elif command == "":
        return
    else:
        print "Invalid command '" + command + "'. Type 'help' for help."

# Create a class to hold the current state
class state_obj(object):
    pass
state = state_obj()
state.artists = False
state.prevroot = None
state.server = []
state.all_servers = []

# Load our class library
execfile("sonictypes.py")

# Make sure the .pysonic folder exists
if not os.path.isdir(os.path.join(os.path.expanduser("~"),".pysonic")):
    os.makedirs(os.path.join(os.path.expanduser("~"),".pysonic"))

# Parse the config file, load (or query) the server data
config = ConfigParser.ConfigParser()
config.read(os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic", "config")))
for one_server in config.sections():

    # Add the new server
    curserver = server(one_server, config.get(one_server,'username'), config.get(one_server,'password'), config.get(one_server,'host'), enabled=config.getboolean(one_server, 'enabled'), jukebox=config.getboolean(one_server, 'jukebox'))
    state.all_servers.append(curserver)

    if curserver.enabled:
        sys.stdout.write("Loading server " + curserver.servername + ": ")
        sys.stdout.flush()

        # Try to load the pickel, build the library if neccessary
        try:
            curserver.library = pickle.load(open(curserver.pickle,"rb"))
        except IOError:
            sys.stdout.write("Building library file.")
            state.artists = curserver.subRequest(page="getArtists", list_type='artist')
            curserver.library.fillArtists(state.artists)
            pickle.dump(curserver.library, open(curserver.pickle,"w"), 2)
            print ""

        # Make sure the server is online
        curserver.goOnline()
    else:
        print "Loading server " + curserver.servername + ": Disabled."

# Create our backup list of servers
for one_server in state.all_servers:
    if one_server.enabled and one_server.online:
        state.server.append(one_server)

# No valid servers
if len(state.server) < 1:
    print "No connections established. Do you have at least one server specified in ~/.pysonic/config and are your username, server URL, and password correct?"
    sys.exit(10)

# If we made it here then it must be!
print "Successfully connected. Entering command mode:"

# Load previous command history
if os.path.exists(os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic","history"))):
    readline.read_history_file(os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic","history")))

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




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
options.history = os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic","history"))


# Pretty print function
def searchResult(information, printy=False, format_string="Nothing to print", fields=()):
    matches = []

    # Go through the XML elements
    for result in information:
        match = True
        # Apply filters to this element
        for tuples in fields:
            if tuples[1]:
                if not tuples[1] in result.attrib[tuples[0]].lower():
                    match = False
        # If this element passed the filters
        if match:
            # Print the result
            if printy:
                tuppies = []
                for x in fields:
                    # Make sure the result is no longer than the specified maxium length
                    if len(x)>2:
                        tuppies.append(result.attrib.get(x[0],'?')[0:x[2]])
                    # Provide a defualt value if one is missing
                    else:
                        tuppies.append(result.attrib.get(x[0],'?'))
                print format_string % tuple(tuppies)
            # Add the result
            matches.append(result)

    state.previous_result = matches

def getMessages():
    """Get chat messages"""
    for one_server in state.server:
        print "On server: " + one_server.servername
        messages =one_server.subRequest(page="getChatMessages", list_type='chatMessage')
        # Convert time from unix time to readable time
        for message in messages:
            message.attrib['time'] = time.ctime(float(message.attrib['time'])/1000).rstrip()
        searchResult(messages, printy=True, format_string="   At %s %s wrote %s.", fields=(('time',None), ('username',None), ('message',None)))

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
        searchResult(playing, printy=True, format_string="   %s minutes ago %s played %s by %s (ID:%s)", fields=(('minutesAgo',None), ('username',None), ('title',None), ('artist',None), ('id',None)))
        state.idtype = 'song'

def stopPlaying():
    """Kill whatever is playing the media"""
    p = subprocess.Popen(['killall', options.player], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    p.wait()

def chooseServer(query=None):
    """Choose whether to display one server or all servers"""
    if query == "all":
        state.server = []
        for one_server in state.all_servers:
            state.server.append(one_server)
        print "All servers restored."
    elif query:
        for one_server in state.all_servers:
            if one_server.servername == query:
                state.server = [one_server]
                print "Selected server " + query + "."
                return
        print "No matching server! Choose from: " + str(",".join(map(lambda x:x.servername, state.all_servers)))
    else:
        if len(state.server) == len(state.all_servers):
            print "All servers enabled. Enter a server name to choose that server."
            print "Choose from: " + str(",".join(map(lambda x:x.servername, state.all_servers)))
        else:
            print "Currently active servers: " + str(",".join(map(lambda x:x.servername, state.server)))
            print "Choose from: " + str(",".join(map(lambda x:x.servername, state.all_servers)))
            print "Specify 'all' to restore all servers, or enter a server name to choose that server."


# Play whatever the previous result was
def playPrevious(play=False):

    # Count the number of results
    results = 0

    # Build the basic VLC args
    vlc_args = [options.player, "--one-instance"]
    vlc_args.append("--no-playlist-enqueue") if play else vlc_args.append("--playlist-enqueue")

    # TODO: Make the magic happen

    # Close the playlist file
    playlist.close()

    # Make sure there is something to play
    if results > 0:
        # Launch the music in VLC
        subprocess.Popen(vlc_args, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    else:
       print "Last command did not result in anything playable."

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
    open(options.history, "wa").close()
    readline.write_history_file(options.history)
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
        listArtist(arg, printy=True)
    elif command == "folder":
        listFolder(query=arg, printy=True)
    elif command == "video":
        listVideo(query=arg, printy=True)
    elif command == "album":
        if arg and arg.isdigit():
            listAlbum(arg, printy=True)
        else:
            print "Please specify album ID. Cannot search or list albums."
    elif command == "song":
        search(arg, printy=True)
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
    elif command == "juke":
        getJukebox()
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
state.previous_result = []
state.idtype = "song"
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
    sys.stdout.write("Loading server " + one_server + ": ")
    sys.stdout.flush()
    curserver = server(one_server, config.get(one_server,'username'), config.get(one_server,'password'), config.get(one_server,'host'), config.getboolean(one_server, 'jukebox'))

    try:
        curserver.library = pickle.load(open(curserver.pickle,"rb"))
        online = curserver.subRequest()
        # Don't add the server to our server list if it crashes out
        if online == 'err':
            continue
        sys.stdout.write("Done!\n")
        sys.stdout.flush()
    except IOError:
        sys.stdout.write("Building library file.")
        state.artists = curserver.subRequest(page="getArtists", list_type='artist', fatal_errors=True)
        curserver.library.fillArtists(state.artists)
        pickle.dump(curserver.library, open(curserver.pickle,"w"), 2)
        print ""
    state.server.append(curserver)

# No valid servers
if len(state.server) < 1:
    print "No connections established. Do you have at least one server specified in ~/.pysonic/config and are your username, server URL, and password correct?"
    sys.exit(10)

# Create our backup list of servers
for one_server in state.server:
    state.all_servers.append(one_server)

# If we made it here then it must be!
print "Successfully connected. Entering command mode:"

# Load previous command history
if os.path.exists(options.history):
    readline.read_history_file(options.history)

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




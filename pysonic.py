#!/usr/bin/python

import sys
import urllib
import urllib2
from optparse import OptionParser, OptionGroup
import xml.etree.ElementTree as ET
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

# Load our type library
execfile("sonictypes.py")

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

# List based on folders
def listFolder(query=None, printy=False):
    if query and query.isdigit():
        childrens =state.server.subRequest(page="getMusicDirectory ", list_type='child', extras={'id':query})
        searchResult(childrens, printy=printy, format_string="%-5s: %s", fields=(('id',None), ('title',None)))
    else:
        folders =state.server.subRequest(page="getIndexes", list_type='artist')
        searchResult(folders, printy=printy, format_string="%-5s: %s", fields=(('id',None), ('name',query)))
        state.idtype = 'artistfolders'

# List videos
def listVideo(query=None, printy=False):
    videos =state.server.subRequest(page="getVideos", list_type='video')
    if query and query.isdigit():
        searchResult(videos, printy=printy, format_string="%-5s|%-17s|%s", fields=(('id',query), ('contentType',None,17), ('title',None,53)))
    else:
        searchResult(videos, printy=printy, format_string="%-5s|%-17s|%s", fields=(('id',None), ('contentType',None,17), ('title',query,53)))
    state.idtype = 'song'

# List based on artists
def listArtists(query=None, printy=False):
    if not state.artists:
        state.artists =state.server.subRequest(page="getArtists", list_type='artist', fatal_errors=True)
    searchResult(state.artists, printy=printy, format_string="%-5s: %s", fields=(('id',None), ('name',query)))
    state.idtype = 'artist'

# List based on artist
def listArtist(query=None, printy=False):
    if query and query.isdigit():
        artist =state.server.subRequest(page="getArtist", list_type='album', extras={'id':query})
        if len(artist) > 0 and printy:
            print artist[0].attrib['artistId'] + ": " + artist[0].attrib['artist']
        searchResult(artist, printy=printy, format_string="   %-4s: %s", fields=(('id',None), ('name',None)))
    elif query is False:
        listArtists(query=query, printy=printy)
    else:
        listArtists(query=query, printy=False)
        for result in state.previous_result:
            listArtist(result.attrib['id'], printy=printy)

# List based on album
def listAlbum(query=None, printy=False):
    songs =state.server.subRequest(page="getAlbum", list_type='song', extras={'id':query})
    if len(songs) > 0 and printy:
        print songs[0].attrib.get('artistId','?') + ": " + songs[0].attrib['artist'] + "\n   " + songs[0].attrib['albumId'] + ": " + songs[0].attrib['album']
    searchResult(songs, printy=printy, format_string="      %4s: %s", fields=(('id',None), ('title',None)))

# List based on search
def search(query=None, printy=False):

    if query and query.isdigit():
        song =state.server.subRequest(page="getSong", list_type='song', extras={'id':query})
        if len(song) > 0 and printy:
            print song[0].attrib.get('artistId','?') + ": " + song[0].attrib.get('artist','?') + "\n   " + song[0].attrib.get('albumId','?') + ": " + song[0].attrib.get('album','?')
        searchResult(song, printy=printy, format_string="      %-4s: %s", fields=(('id',None), ('title',None)))
        if options.verbose:
            print
            names = song[0].attrib.keys()
            for name in names:
                print "%-22s:%s" % (name, song[0].attrib[name][0:57])
    else:
        if query is False:
            query = None
        songs =state.server.subRequest(page="search2", list_type='song', extras={'query':query})
        if len(songs) > 0 and printy:
            print "%-6s %-5s %-5s %-20s %-20s %-20s" % ("SongID", "AlbID", "ArtID", "Song", "Album", "Artist")
        searchResult(songs, printy=printy, format_string="%-6s|%-5s|%-5s|%-20s|%-20s|%-19s", fields=(('id',None), ('albumId',None), ('artistId',None), ('title',None,20), ('album',None,20), ('artist',None,19)))

# Get chat messages
def getMessages():
    messages =state.server.subRequest(page="getChatMessages", list_type='chatMessage')
    # Convert time from unix time to readable time
    for message in messages:
        message.attrib['time'] = time.ctime(float(message.attrib['time'])/1000).rstrip()
    searchResult(messages, printy=True, format_string="At %s %s wrote %s.", fields=(('time',None), ('username',None), ('message',None)))

# Write a chat message
def writeMessage(message):
    messages =state.server.subRequest(page="addChatMessage", list_type='subsonic-response', extras={'message':message})
    if messages[0].attrib['status'] == 'ok':
        print "Successfully wrote message: '" + str(message) + "'"

# Now playing
def nowPlaying():
    playing =state.server.subRequest(page="getNowPlaying", list_type='entry')
    searchResult(playing, printy=True, format_string="%s minutes ago %s played %s by %s (ID:%s)", fields=(('minutesAgo',None), ('username',None), ('title',None), ('artist',None), ('id',None)))
    state.idtype = 'song'

# Now playing
def getJukebox():
    playing =state.server.subRequest(page="jukeboxControl", list_type='entry', extras={'action':'get'})
    searchResult(playing, printy=True, format_string="%s: %s", fields=(('id',None), ('title',None)))

# Kill whatever is playing the media
def stopPlaying():
    p = subprocess.Popen(['killall', options.player], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    p.wait()

# Lets make a separate jukebox method
def jukePlay(action=False):
    if action:
        action = 'set'
    else:
        action = 'add'

    if state.idtype == 'song':
       state.server.subRequest(page="jukeboxControl", list_type='jukeboxStatus', extras={'action':action, 'id':state.previous_result[0].attrib['id']})

    if action == 'set':
       state.server.subRequest(page="jukeboxControl", list_type='jukeboxStatus', extras={'action':'start'})

# Play whatever the previous result was
def playPrevious(play=False):

    # Count the number of results
    results = 0

    # You can't play everything
    if state.idtype == 'artistfolders':
        print "Sorry, it would have required me re-factoring my code to add all folders. (And I'm not about to do that just to allow you to add your whole music library to a playlist.) Fortunately, if you want to do that you still can, just do it this way: 'play artist'."
        return

    # Make sure they aren't derping
    if not (state.idtype == 'artist' or state.idtype == 'album' or state.idtype == 'song' or state.idtype == 'child'):
        print "Last command did not result in anything playable"
        return

    # Build the basic VLC args
    vlc_args = [options.player, "--one-instance"]

    if play:
        vlc_args.append("--no-playlist-enqueue")
    else:
        vlc_args.append("--playlist-enqueue")

    # Open the m3u file
    playlist_file = os.path.join(tempfile.gettempdir(), str(time.time())[-10:-3] + ".m3u")
    vlc_args.append(playlist_file)
    playlist = open(playlist_file, "w")
    playlist.write("#EXTM3U\n")

    # Figure out whether this is an artist, album, song, or folder (child) and add it
    if state.idtype == 'song':
        for song in state.previous_result:
            playlist.write("#EXTINF:" + song.attrib.get('duration','?') + ',' + song.attrib.get('artist','?').encode('utf-8') + ' - ' + song.attrib['title'].encode('utf-8') + "\n")
            playlist.write(state.server.subRequest(page="stream", extras={'id':song.attrib['id']}) + "\n")
            results += 1
    elif state.idtype == 'album':
        for album in state.previous_result[:]:
            listAlbum(album.attrib['id'], printy=False)
            for song in state.previous_result:
                playlist.write("#EXTINF:" + song.attrib.get('duration','?') + ',' + song.attrib['artist'].encode('utf-8') + ' - ' + song.attrib['title'].encode('utf-8') + "\n")
                playlist.write(state.server.subRequest(page="stream", extras={'id':song.attrib['id']}) + "\n")
                results += 1
    elif state.idtype == 'artist':
        for artist in state.previous_result[:]:
            listArtist (artist.attrib['id'], printy=False)
            for album in state.previous_result[:]:
                listAlbum(album.attrib['id'], printy=False)
                for song in state.previous_result:
                    playlist.write("#EXTINF:" + song.attrib.get('duration','?') + ',' + song.attrib['artist'].encode('utf-8') + ' - ' + song.attrib['title'].encode('utf-8') + "\n")
                    playlist.write(state.server.subRequest(page="stream", extras={'id':song.attrib['id']}) + "\n")
                    results += 1
    elif state.idtype == 'child':
        # We must be able to add more things to the list of results to process as we dig deeper
        n = 0
        our_state = state.previous_result[:]
        while n < len(our_state):
            if our_state[n].attrib['isDir'] == "true":
                listFolder(our_state[n].attrib['id'], printy=False)
                our_state.extend(state.previous_result[:])
            else:
                playlist.write("#EXTINF:" + our_state[n].attrib.get('duration','?') + ',' + our_state[n].attrib['artist'].encode('utf-8') + ' - ' + our_state[n].attrib['title'].encode('utf-8') + "\n")
                playlist.write(state.server.subRequest(page="stream", extras={'id':our_state[n].attrib['id']}) + "\n")
                results += 1
            n += 1

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
    open(options.history, "a").close()
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


# If the specified commands as arguments, run them (skip the artist check to save time)
#state.server.subRequest(fatal_errors=True)
#if len(cmd_input) > 0:
#    cmd_input = ' '.join(cmd_input).split(':')
#
#    for cmd in cmd_input:
#        parseInput(cmd.lstrip())
#    sys.exit(0)


# Create a class to hold the current state
class state_obj(object):
    pass
state = state_obj()
state.previous_result = []
state.idtype = "song"
state.artists = False
state.prevroot = None

# Load our class library
execfile("sonictypes.py")

# Parse the config file, load (or query) the server data
config = ConfigParser.ConfigParser()
config.read(os.path.abspath(os.path.join(os.path.expanduser("~"),".pysonic", "config")))
for one_server in config.sections():
    sys.stdout.write("Loading server " + one_server + ": ")
    sys.stdout.flush()
    state.server = server(one_server, config.get(one_server,'username'), config.get(one_server,'password'), config.get(one_server,'host'), config.getboolean(one_server, 'jukebox'))

    try:
        state.server.library = pickle.load(open(state.server.pickle,"rb"))
        state.server.subRequest(fatal_errors=True)
        sys.stdout.write("Done!\n")
        sys.stdout.flush()
    except IOError:
        sys.stdout.write("Building library file.")
        state.artists = state.server.subRequest(page="getArtists", list_type='artist', fatal_errors=True)
        state.server.library.fillArtists(state.artists)
        pickle.dump(state.server.library, open(state.server.pickle,"w"), 2)
        print ""

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




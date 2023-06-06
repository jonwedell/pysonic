import getpass
import os
import sys
import tempfile
import time

import pysonic
from pysonic import utils as utils


def print_messages():
    """Get chat messages. """

    for one_server in pysonic.state.enabled_servers:
        print("On server: " + one_server.server_name)
        messages = one_server.sub_request(page="getChatMessages", list_type='chatMessage')
        # Convert time from unix time to readable time
        for message in messages:
            mtime = time.ctime(float(message.attrib['time']) / 1000).rstrip()
            message.attrib['time'] = mtime
            print("   At %s %s wrote %s." %
                  (message.attrib.get('time', '?'),
                   message.attrib.get('username', '?'),
                   message.attrib.get('message', '?')))


def add_server():
    """Interactively add a new server. """

    user_input_maps = {'y': True,
                       'yes': True,
                       't': True,
                       'true': True,
                       'n': False,
                       'no': True,
                       'f': False,
                       'false': False}

    server_name = ''.join(input("Informal name (one word is best): ").split())
    server_url = input("URL or subsonic username: ")
    user_name = input("Username: ")
    print("Press enter to use secure password mode. (Prompt for password each start.)")
    password = getpass.getpass()
    bitrate = input("Max bitrate (enter 0 to stream raw or press enter to use default value): ")
    enabled = user_input_maps.get(input("Enabled (y/n): ").lower(), True)
    scrobble = user_input_maps.get(input("Scrobble (y/n): ").lower(), False)

    cur_server = pysonic.Server(len(pysonic.state.all_servers), server_name, user_name,
                                password, server_url, enabled, bitrate, scrobble)
    pysonic.state.all_servers.append(cur_server)
    if enabled:
        sys.stdout.write("Initializing server " + cur_server.server_name + ": ")
        sys.stdout.flush()
        cur_server.go_online()
        if cur_server.online:
            pysonic.state.enabled_servers.append(cur_server)


def live():
    """Enter interactive python terminal. """

    import code
    debug_vars = globals()
    debug_vars.update(locals())
    shell = code.InteractiveConsole(debug_vars)
    shell.interact()


def play_previous(play=False):
    """Play whatever the previous result was. """

    # Count the number of results
    results = 0

    # Get the play string
    playlist = ""
    for one_server in pysonic.state.enabled_servers:
        res = one_server.library.play_string()
        results += res[1]
        playlist += res[0]

    # Make sure there is something to play
    if results == 0:
        print("Last command did not result in anything playable.")
        return

    # Create the m3u file
    rel_time = str(time.time())[-10:-3]
    playlist_path = os.path.join(tempfile.gettempdir(), rel_time + ".m3u")
    playlist_file = open(playlist_path, "w")
    playlist_file.write("#EXTM3U\n")
    playlist_file.write(playlist)
    playlist_file.close()

    if play:
        pysonic.state.vlc.write("clear")
        pysonic.state.vlc.write("enqueue " + playlist_path)
    else:
        pysonic.state.vlc.write("enqueue " + playlist_path)
    time.sleep(.1)
    pysonic.state.vlc.write("play")


def print_lyrics(arg):
    """ Prints the lyrics of the current song or a song specified by
    ID. """

    # Get the lyrics of a song by ID
    if arg:
        if arg.isdigit():
            for one_server in utils.iter_servers():
                the_song = one_server.library.get_song_by_id(arg)
                if the_song:
                    print(the_song.get_lyrics())
                else:
                    print("No results.")
        else:
            print("Lyrics search only supported for currently playing song or by specifying song ID.")

    # Get the lyrics of the currently playing song
    else:
        playing_song = get_now_playing()
        if playing_song:
            print(get_now_playing().get_lyrics())
        else:
            print("Nothing is playing.")


def booklet():
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


def print_previous():
    """Print off whatever the saved result is. """

    for one_server in utils.iter_servers():
        if (not one_server.library.prev_res or
                len(one_server.library.prev_res) == 0):
            print("No saved result.")
        else:
            for item in one_server.library.prev_res:
                print(item.recursive_str(level=1, indentations=0))


def choose_server(query=None):
    """Choose whether to display one server or all servers. """

    if query == "all":
        pysonic.state.enabled_servers = []
        for one_server in pysonic.state.all_servers:
            if not one_server.enabled:
                one_server.enabled = True
            if not one_server.online:
                one_server.go_online()
            if one_server.online:
                pysonic.state.enabled_servers.append(one_server)
        print("Using server(s): %s" % ",".join([x.server_name for x in pysonic.state.enabled_servers]))
    elif query:
        queries = set(query.replace(",", " ").split())
        my_result = []
        server_hash = {}
        for one_server in pysonic.state.all_servers:
            server_hash[one_server.server_name] = one_server
        for query in queries:
            if query in server_hash:
                one_server = server_hash[query]
                if not one_server.enabled:
                    one_server.enabled = True
                if not one_server.online:
                    one_server.go_online()
                if one_server.online:
                    my_result.append(one_server)
                    print("Selected server " + query + ".")
            else:
                print(f"No matching server ({query})! Choose from: " +
                      ",".join([x.server_name for x in pysonic.state.all_servers]))
        if len(my_result) > 0:
            pysonic.state.enabled_servers = my_result
        else:
            print("No servers matched your results.")
        print("Using server(s): %s" % ",".join([x.server_name for x in pysonic.state.enabled_servers]))
        # Make sure that only enabled servers are enabled
        for one_server in pysonic.state.all_servers:
            one_server.enabled = False
        for one_server in pysonic.state.enabled_servers:
            one_server.enabled = True
    else:
        if len(pysonic.state.enabled_servers) == len(pysonic.state.all_servers):
            print("All servers enabled. Enter a server name to choose that server.")
            print("Choose from: %s" % ",".join([x.server_name for x in pysonic.state.all_servers]))
        else:
            print("Currently active servers: %s" % ",".join([x.server_name for x in pysonic.state.enabled_servers]))
            print("All known servers: %s" % ",".join([x.server_name for x in pysonic.state.all_servers]))
            print("Type 'server all' to restore all servers, or enter server names to select.")


def now_playing():
    """Get the now playing lists. """

    for one_server in pysonic.state.enabled_servers:
        print("On server: " + one_server.server_name)
        playing = one_server.sub_request(page="getNowPlaying", list_type='entry')
        for one_person in playing:
            ag = one_person.attrib.get
            print(f"   {ag('minutesAgo', '?')} minutes ago {ag('username', '?')} played {ag('title', '?')} by "
                  f"{ag('artist', '?')} (ID:{ag('id', '?')})")
            one_server.library.get_song_by_id(one_person.attrib['id'])


def get_now_playing():
    """ Returns the song that is currently playing. """

    stream_info = pysonic.state.vlc.read_write("status")

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

    return pysonic.state.all_servers[stream_id].library.get_song_by_id(song_id)


def write_message(message):
    """Write a chat message. """

    for one_server in pysonic.state.enabled_servers:
        print("On server: " + one_server.server_name)
        messages = one_server.sub_request(page="addChatMessage",
                                          list_type='subsonic-response',
                                          extras={'message': message})
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
        playing_song.server.library.print_similar_songs(similar_id, arg)
        return

    split_args = str(arg).split()
    if split_args[0] == "song":
        if len(split_args) == 1:
            print("Please specify the ID of a song to find similar songs for.")
            return
        for one_server in utils.iter_servers():
            one_server.library.print_similar_songs(*split_args[1:])
    elif split_args[0] == "artist":
        print("Not yet implemented.")
    else:
        print("Please specify 'song', 'artist', or a number of similar songs "
              "to the now playing song to return.")

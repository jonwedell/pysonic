import cmd
import os
import sys

import pysonic
import pysonic.commands as commands
import pysonic.utils as utils


class PysonicShell(cmd.Cmd):
    intro = 'Successfully connected. Type help or ? to list commands.\n'
    prompt = ':'

    def do_artist(self, arg):
        """artist [ID|query] - display artists matching ID or query"""
        for one_server in utils.iter_servers():
            one_server.library.search_artists(arg)

    def do_album(self, arg):
        """album [ID|query] - displays albums matching ID or query."""
        for one_server in utils.iter_servers():
            one_server.library.search_albums(arg)

    def do_folder(self, arg):
        """folder [ID|query] - displays folders matching ID or query."""
        for one_folder in utils.iter_servers():
            one_folder.library.search_folders(arg)

    def do_song(self, arg):
        """song [ID|query] - display songs matching ID or query."""
        for one_server in utils.iter_servers():
            one_server.library.search_songs(arg)

    def do_playlist(self, arg):
        """playlist [ID|query]' - display playlists matching ID or query."""
        for one_server in utils.iter_servers():
            one_server.library.search_playlists(arg)

    def do_rebuild(self, _):
        """rebuild - rebuild the library for any active servers."""
        for one_server in utils.iter_servers():
            os.unlink(utils.get_home(one_server.pickle_file))
            one_server.library.initialized = False
            one_server.go_online()

    def do_new(self, arg):
        """new [num_results] - prints new albums added to the server."""
        for one_server in utils.iter_servers():
            one_server.library.get_special_albums(number=arg)

    def do_rand(self, arg):
        """rand [num_results] - prints a random list of albums from the server."""
        for one_server in utils.iter_servers():
            one_server.library.get_special_albums(album_type='random', number=arg)

    def do_similar(self, arg):
        """similar [song] [num_results] - displays a list of songs similar to
        the specified song."""
        commands.get_similar(arg)

    def do_server(self, arg):
        """server - switch active servers. Run with no args for help."""
        commands.choose_server(arg)

    def do_add_server(self, _):
        """add_server - interactively add a new server."""
        commands.add_server()

    def do_now(self, _):
        """now - shows who is currently listening to what on subsonic."""
        commands.now_playing()

    def do_pause(self, _):
        """pause - pause the music"""
        pysonic.state.vlc.write("pause")

    def do_resume(self, _):
        """resume - resume paused music"""
        pysonic.state.vlc.write("play")

    def do_next(self, _):
        """next - skip to the next track"""
        pysonic.state.vlc.write("next")
        print(commands.get_now_playing())

    def do_prev(self, _):
        """prev - return to the previous track"""
        pysonic.state.vlc.write("prev")
        print(commands.get_now_playing())

    def do_list(self, _):
        """list - display the current playlist"""
        print(pysonic.state.vlc.read_write("playlist"))

    def do_clear(self, _):
        """clear - clear the playlist"""
        pysonic.state.vlc.write("clear")

    def do_playing(self, _):
        """playing - shows what is currently playing on the local machine."""
        print(commands.get_now_playing())

    def do_vlc(self, _):
        """vlc - drop into a direct connection with the VLC CLI"""
        print("Entering VLC shell:")
        sys.stdout.write(":")
        sys.stdout.flush()
        pysonic.state.vlc.telnet_con.interact()
        print("\nReturned to pysonic shell:")

    def do_goto(self, arg):
        """goto ID - go to item with ID in playlist"""
        pysonic.state.vlc.write("goto " + arg)
        now_playing = pysonic.state.vlc.read()
        if now_playing != "":
            print(now_playing)
        else:
            print(commands.get_now_playing())

    def do_play(self, arg):
        """play [artist|album|song query|ID] - play whatever the artist,
        album, or song query turns up immediately. (Play previous result
         if no arguments.)"""
        if arg:
            self.redispatch(arg)

        commands.play_previous(play=True)

    def do_queue(self, arg):
        """queue [artist|album|song query|ID] - queue whatever the artist,
        album, or song query turns up. (Queue previous result if no arguments.)"""
        if arg:
            self.redispatch(arg)
        commands.play_previous()

    def do_live(self, _):
        """live - drop into a python shell"""
        commands.live()

    def do_result(self, _):
        """result - print whatever matched the previous query."""
        commands.print_previous()

    def do_lyrics(self, arg):
        """lyrics [songID] - print the lyrics of the currently playing song
        or if specified, the song specified by songID."""
        commands.print_lyrics(arg)

    def do_booklet(self, _):
        """booklet - continually show the lyrics of the currently playing song."""
        commands.booklet()

    def do_write(self, arg):
        """write message - write message to the subsonic chat."""
        commands.write_message(arg)

    def do_read(self, _):
        """read - displays subsonic chat messages."""
        commands.print_messages()

    def do_vlchelp(self, _):
        """vlchelp - display additional help on VLC commands."""
        print(pysonic.state.vlc.read_write("help"))

    def do_seek(self, arg):
        """seek time - seeks to the specified time in the current song"""
        print(pysonic.state.vlc.read_write(f"seek {arg}"))

    def do_get_time(self, arg):
        """get_time - shows the time into the currently playing song"""
        print(pysonic.state.vlc.read_write(f"get_time {arg}"))

    def do_quit(self, _):
        """quit - quit pysonic"""
        sys.exit(0)

    def do_EOF(self, _):
        """Exit"""
        sys.exit(0)

    def redispatch(self, arg):
        split = arg.split(' ')
        command = f'do_{split[0]}'
        method_list = [func for func in dir(self) if callable(getattr(self, func))]
        if command in method_list:
            args = " ".join(split[1:])
            function = getattr(self, command)
            function(args)

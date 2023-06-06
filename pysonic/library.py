import random
import time
from datetime import datetime
from functools import cached_property
from typing import List, Optional, Iterable
from urllib.parse import urlencode

import pysonic


class Library(object):
    """This class implements the logical concept of a library. """

    artists = []
    initialized = False

    def __init__(self, server: 'pysonic.Server' = None):
        if server is None:
            raise ValueError("You must specify a corresponding server for this library.")
        self.artists = []
        self.server = server
        self.folder = None
        self.artist_ids = None
        self.song_ids = None
        self.album_ids = None
        self.last_update = None
        self.prev_res = []

    def update_server(self, server: Optional['pysonic.Server']) -> None:
        """Update the server this library is linked to. """
        self.server = server
        for one_artist in self.artists:
            one_artist.update_server(server)
        # TODO: Update folders also.

    def add_artist(self, artist_id: str) -> bool:
        """Add an artist to the library. """

        new_artist = pysonic.Artist(artist_id, server=self.server)
        if new_artist:
            self.artists.append(new_artist)
            return True
        else:
            return False

    def update_ids(self) -> None:
        """Calculate a list of all song, album, and artist ids. """

        self.album_ids = [x.data_dict['id'] for x in self.albums]
        self.artist_ids = [x.data_dict['id'] for x in self.artists]
        self.song_ids = [x.data_dict['id'] for x in self.songs]

    def update_library(self) -> int:
        """Check for new albums and artists. Return number of changes"""

        updates = 0

        self.update_ids()
        new_albums = self.server.sub_request(page="getAlbumList2",
                                             list_type='album',
                                             extras={'type': 'newest', 'size': 50})

        for one_album in new_albums:
            if one_album.attrib['artistId'] not in self.artist_ids:
                if self.add_artist(one_album.attrib['artistId']):
                    self.update_ids()
            elif one_album.attrib['id'] not in self.album_ids:
                artist = self.get_artist_by_id(one_album.attrib['artistId'])
                artist.add_albums([one_album])
                self.update_ids()
                print(artist.recursive_str())
                updates += 1
        self.last_update = time.time()

        # Clear the cached properties
        self.__dict__.pop('songs', None)
        self.__dict__.pop('albums', None)
        return updates

    def fill_artists(self) -> None:
        """Query the server for all the artists and albums. """

        for one_artist in self.server.sub_request(page="getArtists", list_type='artist'):
            self.add_artist(one_artist.attrib['id'])
        self.initialized = True

    def play_string(self, playable_list: 'pysonic.Playable' = None) -> (str, int):
        """Return the needed playlist data, and the number of items in the playlist. """

        # Make sure they have something to play
        if not hasattr(self, 'prev_res') or not self.prev_res:
            return "", 0

        res_string = ""
        num_ret = 0

        if playable_list:
            for item in playable_list:
                res_string += item.play_string()
                num_ret += 1
            return res_string, num_ret
        else:
            for item in self.prev_res:
                res_string += item.play_string()
                num_ret += 1
            return res_string, num_ret

    def recursive_str(self, level: int = 5, indentations: int = 0) -> str:
        """Prints children up to level n. """

        res = ""
        if indentations > 0:
            res = "   " * indentations
        if level > 0:
            for one_artist in self.artists:
                res += "\n" + one_artist.recursive_str(level - 1, indentations + 1)
        return res

    def print_similar_songs(self, song_id: str, count=10) -> None:
        """ Finds a list of similar songs. """

        try:
            song_id = int(song_id)
        except ValueError:
            print("You must provide a song ID and not a song name for the similar query.")
            return

        similar = self.server.sub_request(page="getSimilarSongs",
                                          list_type="song",
                                          extras={'id': song_id, 'count': count})
        similar = [pysonic.Song(x.attrib, self.server) for x in similar]
        self.prev_res = similar
        pysonic.print_song_list(similar)

    @cached_property
    def songs(self) -> List['pysonic.Song']:
        """Return a list of all songs in the library. """

        ret_songs = []
        for one_artist in self:
            for one_album in one_artist:
                for one_song in one_album:
                    ret_songs.append(one_song)
        return ret_songs

    @cached_property
    def albums(self) -> List['pysonic.Album']:
        """Return a list of all albums in the library. """

        ret_albums = []
        for one_artist in self:
            for one_album in one_artist:
                ret_albums.append(one_album)
        return ret_albums

    def get_scrobble_url(self, song_id: str) -> str:
        """ Returns the URL to fetch in order to scrobble a song. """

        server = self.server
        server.generate_md5_password()

        # Add request specific parameters to our hash
        params = server.default_params.copy()
        params.update({'id': song_id})

        # Encode our parameters and send the request
        params = urlencode(params)

        # Encode the URL
        url = server.server_url.rstrip() + "scrobble.view" + "?" + params

        return url

    def get_song_by_id(self, song_id: str) -> Optional['pysonic.Song']:
        """Fetch a song from the library based on its ID. """
        for one_song in self.songs:
            if one_song.data_dict['id'] == str(song_id):
                self.prev_res = [one_song]
                return one_song
        self.prev_res = []
        return None

    def get_artist_by_id(self, artist_id: str) -> Optional['pysonic.Artist']:
        """Return an artist based on ID. """

        for one_artist in self.artists:
            if one_artist.data_dict['id'] == str(artist_id):
                return one_artist
        return None

    def get_album_by_id(self, album_id: str) -> Optional['pysonic.Album']:
        """Return an album based on ID. """

        for one_album in self.albums:
            if one_album.data_dict['id'] == str(album_id):
                return one_album
        return None

    def search_songs(self, search: str = None, store_only: bool = False) -> None:
        """Search through song names or ids for the query. """

        if search:
            res = []

            chunks = search.split(" ")
            # They are searching by one or more ID
            if all(x.isdigit() for x in chunks):
                for chunk in chunks:
                    for one_song in self.songs:
                        if one_song.data_dict['id'] == chunk:
                            res.append(one_song)
            else:
                for one_song in self.songs:
                    if search.lower() in one_song.data_dict['title'].lower():
                        res.append(one_song)
        else:
            res = self.songs

        self.prev_res = res

        if store_only:
            return

        # If they want all songs, only print the song names
        if not search:
            for one_song in res:
                print(one_song.recursive_str(0))

        # There is a query
        else:
            pysonic.print_song_list(res)

    def search_playlists(self, search: str = None) -> None:
        """Search through playlists. """

        matches = []

        def id_sort(playlist):
            return playlist.attrib['id']

        res = sorted(self.server.sub_request(page="getPlaylists", list_type="playlist"), key=id_sort)

        # ID search
        if search and all(x.isdigit() for x in search):
            for x in res:
                if x.attrib['id'] == search:
                    self.prev_res = [pysonic.Playlist(x, self.server)]
                    print(self.prev_res[0].recursive_print(1))
        else:
            for x in res:
                if not search or search.lower() in x.attrib['name'].lower():
                    the_playlist = pysonic.Playlist(x, self.server)
                    matches.append(the_playlist)
            self.prev_res = matches
            if len(self.prev_res) == 1:
                print(self.prev_res[0].recursive_print(1))
            else:
                for match in self.prev_res:
                    print(match.recursive_print())

    def search_albums(self, search: str = None) -> None:
        """Search through albums names or ids for the query. """

        if search:
            res = []

            # See if they are adding multiple album by ID
            chunks = search.split(" ")
            if all(x.isdigit() for x in chunks):
                for chunk in chunks:
                    for one_album in self.albums:
                        if one_album.data_dict['id'] == chunk:
                            res.append(one_album)
            else:
                for one_album in self.albums:
                    if search.lower() in one_album.data_dict['name'].lower():
                        res.append(one_album)
        else:
            res = self.albums

        self.prev_res = res

        # Print the results
        if len(res) == 0:
            print("No albums matched your query.")
            return
        for one_album in res:
            if search:
                print(one_album)
            else:
                print(one_album.recursive_str(0))

    def search_artists(self, search: str = None) -> None:
        """Search through artists names or ids for the query. """

        if search:
            res = []

            chunks = search.split(" ")
            # They are searching by one or more ID
            if all(x.isdigit() for x in chunks):
                for chunk in chunks:
                    for one_artist in self.artists:
                        if one_artist.data_dict['id'] == chunk:
                            res.append(one_artist)

            # They are searching by name
            else:
                for one_artist in self.artists:
                    if search.lower() in one_artist.data_dict['name'].lower():
                        res.append(one_artist)
        else:
            res = self.artists

        self.prev_res = res

        # Print the results
        if len(res) == 0:
            print("No artists matched your query.")
            return
        for one_artist in res:
            if search:
                print(one_artist.recursive_str(1))
            else:
                print(one_artist.recursive_str(0))

    def search_folders(self, search: str = None) -> None:
        """ Search through the folders for the query or id. """

        if not hasattr(self, 'folder') or self.folder is None:
            print("Building folder...")
            self.folder = pysonic.Folder(server=self.server)
            # Pickle the new library
            self.server.pickle()

        res = []
        if search:

            for one_folder in self.folder.get_subfolders:
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
                print(one_folder.recursive_str(1))
            else:
                print(one_folder.recursive_str(0))

    def get_special_albums(self, album_type: str = 'newest', number: int = 10) -> None:
        """Returns either new or random albums. """

        # Process the supplied number
        if not number or not str(number).isdigit():
            number = 10
        else:
            number = int(number)

        if album_type == 'random':
            albums = self.albums
            if len(albums) < number:
                number = len(albums)
            res = random.sample(albums, number)
        elif album_type == 'newest':
            res = sorted(self.albums, reverse=True, key=lambda k: k.data_dict.get('created', '?'))[:number]
        else:
            raise ValueError("Invalid type to search for.")

        self.prev_res = res
        for item in self.prev_res:
            print(item.special_print())

    # Implement expected methods
    def __iter__(self) -> Iterable:
        return iter(self.artists)

    def __len__(self) -> int:
        return len(self.artists)

    def __str__(self) -> str:
        return self.recursive_str(1, -1)

    def __repr__(self) -> str:
        return f"Library(server={repr(self.server)}, last_update='{datetime.fromtimestamp(self.last_update).strftime('%Y-%m-%d %H:%M:%S')}')"

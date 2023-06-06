import sys
from typing import Iterable

import pysonic
import pysonic.utils as utils


class Album(object):
    """This class implements the logical concept of an album. """

    data_dict = None
    songs = []

    def __init__(self, data_dict, server: 'pysonic.Server' = None):
        """We need the dictionary to create an album. """

        self.songs = []
        self.server = server
        if data_dict:
            self.data_dict = data_dict
            songs = self.server.sub_request(page="getAlbum",
                                            list_type='song',
                                            extras={'id': self.data_dict['id']})

            # Sort the songs by track number and disk
            songs.sort(key=lambda k: (int(k.attrib.get('discNumber', sys.maxsize)), int(k.attrib.get('track', sys.maxsize))))

            if not server.library.initialized:
                sys.stdout.write('.')
                sys.stdout.flush()
            for one_song in songs:
                self.songs.append(pysonic.Song(one_song.attrib, server=self.server))
        else:
            raise ValueError('You must pass the album dictionary to create an album.')

    def update_server(self, server: 'pysonic.Server') -> None:
        """Update the server this album is linked to. """
        self.server = server
        for one_song in self.songs:
            one_song.update_server(server)

    def play_string(self) -> str:
        """Return the needed playlist data. """

        playlist = ""
        for one_song in self.songs:
            playlist += one_song.play_string()
        return playlist

    def recursive_str(self, level: int = 5, indentations: int = 0) -> str:
        """Returns the string representation of children up to level n. """

        album_name = utils.clean_get(self, 'name')
        album_name = album_name[0:utils.get_width(6 + 3 * indentations)]
        res = "%-4s: %s" % (utils.clean_get(self, 'id'), album_name)
        if indentations > 0:
            res = "   " * indentations + res
        if level > 0:
            for one_song in self.songs:
                res += "\n" + one_song.recursive_str(indentations + 1)
        return res

    def special_print(self) -> str:
        """ Used to print albums in list rather than hierarchical format. """

        format_str = "%4s: %-20s %-3s: %-3s"
        return format_str % (utils.clean_get(self, 'artistId'),
                             utils.clean_get(self, 'artist')[0:20],
                             utils.clean_get(self, 'id'),
                             utils.clean_get(self, 'name')[0:utils.get_width(35)])

    # Implement expected methods
    def __iter__(self) -> Iterable:
        return iter(self.songs)

    def __len__(self) -> int:
        return len(self.songs)

    def __str__(self) -> str:
        return "%-3s: %s\n%s" % \
               (utils.clean_get(self, 'artistId'),
                utils.clean_get(self, 'artist')[0:utils.get_width(5)],
                self.recursive_str(1, 1))

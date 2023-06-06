from typing import List

import pysonic
import pysonic.lyrics
import pysonic.utils as utils


class Song(object):
    """This class implements the logical concept of a song. """

    data_dict = None

    def __init__(self, data_dict, server: 'pysonic.Server' = None):
        """We need the dictionary to create a song. """

        self.server = server
        if data_dict:
            self.data_dict = data_dict
        else:
            raise ValueError('You must pass the song dictionary to create a song.')

    def update_server(self, server: 'pysonic.Server') -> None:
        """Update the server this song is linked to. """

        self.server = server

    def play_string(self) -> str:
        """Return the playlist string. """

        extras_dict = {'id': self.data_dict['id']}
        if self.server.bitrate == 0:
            extras_dict['format'] = "raw"
        elif self.server.bitrate is not None:
            extras_dict['maxBitRate'] = self.server.bitrate

        if self.server.scrobble:
            library = self.server.library
            scrobble_str = "#EXTINF:0,LastFM - This scrobbles %s\n%s" % (
                utils.clean_get(self, 'title'),
                library.get_scrobble_url(utils.clean_get(self, 'id')))
        else:
            scrobble_str = ""

        return "#EXTINF:%s,%s - %s\n%s\n%s\n" % (
            utils.clean_get(self, 'duration'),
            utils.clean_get(self, 'artist'),
            utils.clean_get(self, 'title'),
            self.server.sub_request(page="stream", extras=extras_dict),
            scrobble_str)

    def __str__(self) -> str:
        return "%-3s: %s\n   %-4s: %s\n      %-5s: %s" % \
               (utils.clean_get(self, 'artistId'),
                utils.clean_get(self, 'artist')[0:utils.get_width(5)],
                utils.clean_get(self, 'albumId'),
                utils.clean_get(self, 'album')[0:utils.get_width(9)],
                utils.clean_get(self, 'id'),
                utils.clean_get(self, 'title')[0:utils.get_width(13)])

    def __repr__(self) -> str:
        return f"Song(title='{self.data_dict.get('title')}', id={self.data_dict.get('id')})"

    def get_details(self, show_header: bool = False):
        """Print in a columnar mode that works well with multiple songs. """

        total_space = utils.get_width(21)
        available_space = int(total_space / 3)
        remainder = total_space % 3

        if show_header:
            header_format = f"%-6s|%-5s|%-5s|%-{available_space}s|%-{available_space}s|%-{available_space + remainder}s"
            print(header_format % ("SongID", "AlbID", "ArtID", "Song", "Album", "Artist"))

        format_string = f"%-6s|%-5s|%-5s|%-{available_space}s|%-{available_space}s|%-{available_space + remainder}s"
        return format_string % (
            utils.clean_get(self, 'id'),
            utils.clean_get(self, 'albumId'),
            utils.clean_get(self, 'artistId'),
            utils.clean_get(self, 'title')[:available_space],
            utils.clean_get(self, 'album')[:available_space],
            utils.clean_get(self, 'artist')[:available_space + remainder])

    def get_lyrics(self) -> str:
        """ Returns the lyrics of the song as a string as provided by
        the subsonic server. """

        try:
            artist, title, lyrics = pysonic.lyrics.get_lyrics(utils.clean_get(self, 'title'),
                                                              utils.clean_get(self, 'artist'))
        except Exception as e:
            return "Error when fetching lyrics: %s" % str(e)

        if lyrics:
            return "%s | %s\n%s\n%s" % (artist, title, "-" * utils.get_width(), lyrics)
        else:
            return "No lyrics available."

    # Though the IDE will tell you level isn't used, it's lying. (Can be called from `result` command.)
    def recursive_str(self, indentations: int = 0, level: int = 0) -> str:
        """Returns the string representation of children up to level n. """

        max_len = utils.get_width(7 + 3 * indentations)
        res = "%-5s: %s" % (utils.clean_get(self, 'id'), utils.clean_get(self, 'title')[0:max_len])
        if indentations > 0:
            res = "   " * indentations + res
        return res


def print_song_list(song_list: List['pysonic.Song']) -> None:
    """ Nicely formats and prints a list of songs. """

    if len(song_list) == 0:
        print("No songs matched your query.")
        return
    if utils.get_width() >= 80:
        show_header = True
        for one_song in song_list:
            print(one_song.get_details(show_header=show_header))
            show_header = False
    else:
        print("For optimal song display, please resize terminal to be at least 80 characters wide.")
        for one_song in song_list:
            print(one_song)

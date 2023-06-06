from typing import Iterable

import pysonic
import pysonic.utils as utils


class Artist(object):
    """This class implements the logical concept of an artist. """

    data_dict = None
    albums = []

    def add_albums(self, albums: 'pysonic.album') -> None:
        """Add any number of albums to the artist. """

        for one_album in albums:
            self.albums.append(pysonic.Album(one_album.attrib, server=self.server))

    def update_server(self, server: 'pysonic.Server') -> None:
        """Update the server this artist is linked to. """

        self.server = server
        for one_album in self.albums:
            one_album.update_server(server)

    def __init__(self, artist_id: str = None, server: 'pysonic.Server' = None):
        """We need the dictionary to create an artist. """

        self.albums = []
        self.server = server

        if artist_id is not None:
            # Fetch the whole XML tree for this artist
            data_dict = self.server.sub_request(page="getArtist",
                                                list_type='album',
                                                extras={'id': artist_id},
                                                return_root=True)

            if data_dict == "err":
                raise ValueError("Could not get artist data from server.")

            if len(data_dict) == 1:
                self.data_dict = data_dict[0].attrib
                self.add_albums(list(data_dict[0]))
            else:
                print(data_dict)
                raise ValueError('The root you passed includes more than one artist.')
            # Sort the albums by ID
            self.albums.sort(key=lambda k: int(k.data_dict.get('id', '0')))
        else:
            raise ValueError('You must pass the artist dictionary to create an artist.')

    def __repr__(self) -> str:
        return f"Artist(name='{self.data_dict.get('name')}', id={self.data_dict.get('id')})"

    def play_string(self) -> str:
        """Return the needed playlist data. """

        playlist = ""
        for one_album in self.albums:
            playlist += one_album.play_string()
        return playlist

    def recursive_str(self, level: int = 3, indentations: int = 0) -> str:
        """Returns the string representation of children up to level n. """

        max_len = utils.get_width(5 + 3 * indentations)
        res = "%-3s: %s" % (utils.clean_get(self, 'id'), utils.clean_get(self, 'name')[0:max_len])
        if indentations > 0:
            res = "   " * indentations + res
        if level > 0:
            for one_album in self.albums:
                res += "\n" + one_album.recursive_str(level - 1, indentations + 1)
        return res

    # Implement expected methods
    def __iter__(self) -> Iterable:
        return iter(self.albums)

    def __len__(self) -> int:
        return len(self.albums)

    def __str__(self) -> str:
        return self.recursive_str(0)

import pysonic


class Playlist(object):
    """ A class for a playlist. """

    id = None
    name = None
    songs = []

    def __init__(self, data_dict, server: 'pysonic.Server' = None):
        """We need the dictionary to create a song. """

        self.server = server
        if data_dict is None:
            raise ValueError('You must pass a playlist element to create a playlist.')
        else:
            self.id = data_dict.attrib['id']
            self.name = data_dict.attrib['name']
            self.songs = []

            self.songs = [self.server.library.get_song_by_id(x.attrib['id']) for x in
                          self.server.sub_request(page="getPlaylist", list_type="entry", extras={'id': self.id})]

    def play_string(self) -> str:
        """ Create a play string for the playlist. """

        playlist_string = ""
        for song in self.songs:
            playlist_string += song.play_string()
        return playlist_string

    def __str__(self) -> str:
        return "%-1s: %s" % (self.id, self.name)

    def recursive_print(self, level: int = 0) -> str:
        if level == 0:
            return "%-1s: %s" % (self.id, self.name)
        else:
            res = self.recursive_print(0)
            for song in self.songs:
                res += '\n' + song.recursive_str(1, 1)
            return res

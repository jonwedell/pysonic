from functools import cached_property
from typing import List, Iterable

import pysonic
import pysonic.utils as utils


class Folder(object):
    """This class implements the logical concept of a folder."""

    data_dict = None
    children = []
    songs = []

    def __init__(self, server: 'pysonic.Server' = None, folder_id: str = None, data_dict: dict = None):
        """Create a folder hierarchy. Recursively calls itself with
        fold_id set to build the tree. """

        self.children = []
        self.songs = []
        self.data_dict = data_dict
        self.server = server

        if folder_id:
            children = self.server.sub_request(page="getMusicDirectory ", list_type='child', extras={'id': folder_id})
            for child in children:
                if (child.attrib['isDir'] == "true" and
                        child.attrib['title'][-5:] != ".flac" and
                        child.attrib['title'][-4:] != ".mp3"):
                    print("Found directory: %s" %
                          child.attrib['title'][0:utils.get_width(17)])
                    self.children.append(Folder(server=self.server,
                                                folder_id=child.attrib['id'],
                                                data_dict=child.attrib))

                elif child.attrib['isDir'] == "true":
                    print("Skipping (subsonic bug): %s" % child.attrib['title'][0:utils.get_width(25)])
                else:
                    if child.attrib['id'] in self.server.library.song_ids:
                        song_id = child.attrib['id']
                        song = self.server.library.get_song_by_id(song_id)
                        self.songs.append(song)
                    else:
                        print("Found new song: %s" %
                              child.attrib['title'][0:utils.get_width(16)])
                        self.songs.append(pysonic.Song(child.attrib, server=self.server))
        else:
            server.library.update_ids()
            folders = self.server.sub_request(page="getIndexes", list_type='artist')
            for one_folder in folders:
                self.children.append(Folder(server=self.server,
                                            folder_id=one_folder.attrib['id'],
                                            data_dict=one_folder.attrib))

    def play_string(self) -> str:
        """Return the needed playlist data. """

        playlist = ""
        for child in self.children:
            playlist += child.play_string()
        for one_song in self.songs:
            playlist += one_song.play_string()
        return playlist

    def update_server(self, server: 'pysonic.Server') -> None:
        """Update the server this folder is linked to. """

        self.server = server
        for child in self.children:
            child.update_server(server)
        for one_song in self.songs:
            one_song.update_server(server)

    def recursive_str(self, level: int = 5, indentations: int = 0) -> str:
        """Prints children up to level n. """

        if self.data_dict is not None:
            name_title = utils.clean_get(self, 'title')
            name_title = name_title[0:utils.get_width(6)]
            if name_title == "?":
                name_title = utils.clean_get(self, 'name')
                name_title = name_title[0:utils.get_width(6)]
            res = "%-4s: %s" % (utils.clean_get(self, 'id'), name_title)
            if indentations > 0:
                res = "   " * indentations + res
        else:
            res = "   " * indentations

        if level > 0:
            for child in self.children:
                res += "\n" + child.recursive_str(level - 1, indentations + 1)
            for one_song in self.songs:
                res += "\n" + one_song.recursive_str(level - 1, indentations + 1)
        return res

    @cached_property
    def get_subfolders(self) -> List['pysonic.Folder']:
        """ Get any subfolders from this folder. """

        folder_list = []
        for child in self.children:
            if child is not None:
                folder_list.append(child)
                folder_list.extend(child.get_subfolders)
        return folder_list

    # Implement expected methods
    def __iter__(self) -> Iterable:
        return iter(self.children)

    def __len__(self) -> int:
        return len(self.children)

    def __str__(self) -> str:
        return self.recursive_str(1)

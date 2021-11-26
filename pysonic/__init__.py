import pysonic.utils as utils
import pysonic.lyrics as lyrics
from pysonic.dataclasses import State
from pysonic.song import Song, print_song_list
from pysonic.folder import Folder
from pysonic.album import Album
from pysonic.artist import Artist
from pysonic.library import Library
from pysonic.server import Server
from pysonic.playlist import Playlist
from pysonic.types import Playable
from pysonic.vlc import VLCInterface
from pysonic.context import PysonicContext

# Use a dictionary to hold the state
state = State()
options = None

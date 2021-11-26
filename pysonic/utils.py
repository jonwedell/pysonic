import os
import random
import re
import stat
import string

import pysonic


def get_home(file_name: str = None):
    """ Returns the .pysonic directory location (full path) and
    if filename is specified returns the .pysonic directory plus
    that filename."""

    if pysonic.state.root_dir:
        home_dir = pysonic.state.root_dir
    else:
        home_dir = os.path.abspath(os.path.join(os.path.expanduser("~"), ".pysonic/"))

    if file_name:
        return os.path.join(home_dir, file_name)
    else:
        return home_dir


def salt_generator(size=10, chars=string.ascii_uppercase + string.digits):
    """ Generates a random ASCII string (or string from whatever source
    you provide in chars) of length size. """

    return ''.join(random.SystemRandom().choice(chars) for _ in range(size))


def clean_get(obj, key):
    """ Returns a key with the song dictionary with the necessary
    changes made to properly display missing values and non-utf8
    results. """

    return obj.data_dict.get(key, '?')


def natural_sort(sort_list):
    def convert(text):
        return int(text) if text.isdigit() else text.lower()

    def alphanum_key(key):
        return [convert(c) for c in re.split('([0-9]+)', key)]

    return sorted(sort_list, key=alphanum_key)


def get_width(used=0):
    """Get the remaining width of the terminal. """

    # Return the remaining terminal width
    return int(pysonic.state.cols) - used


# Update terminal size when window is resized
def update_width(_=None, __=None):
    """ The terminal has resized, so figure out the new size."""

    # Check if we are outputting to a terminal style device
    mode = os.fstat(0).st_mode
    if stat.S_ISFIFO(mode) or stat.S_ISREG(mode):
        pysonic.state.cols = 10000
    else:
        pysonic.state.cols = int(os.popen('stty size', 'r').read().split()[1])


def iter_servers():
    """A generator that goes through the active servers. """

    show_cur_server = False
    if len(pysonic.state.enabled_servers) > 1:
        show_cur_server = True

    for one_server in pysonic.state.enabled_servers:
        if show_cur_server:
            print("On server: " + one_server.server_name)
        yield one_server

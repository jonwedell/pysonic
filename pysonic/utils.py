import os
import random
import string


def get_home(filename=None):
    """ Returns the .pysonic directory location (full path) and
    if filename is specified returns the .pysonic directory plus
    that filename. """

    home_dir = os.path.abspath(os.path.join(os.path.expanduser("~"), ".pysonic/"))

    if filename:
        return os.path.join(home_dir, filename)
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



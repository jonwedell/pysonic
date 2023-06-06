import getpass
import hashlib
import logging
import os
import pickle
import sys
from binascii import hexlify
from typing import List, Union
from xml.etree import ElementTree as ETree
from xml.etree.ElementTree import Element

import requests
from requests import Request
from requests.adapters import HTTPAdapter, Retry

import pysonic
import pysonic.utils as utils
from pysonic.exceptions import PysonicException


class Server(object):
    """This class represents a server. It stores the password and makes
    queries. """

    session: requests.Session = None

    def __init__(self, server_id,
                 server_name: str,
                 user_name: str,
                 password: str,
                 server_url: str,
                 enabled: bool = True,
                 bitrate: str = None,
                 scrobble: bool = False):
        """A server object. """

        # Build the default parameters into a reusable hash
        self.default_params = {
            'u': user_name,
            'v': "1.13.0",
            'c': "subsonic-cli",
            'f': "xml",
            'sid': server_id
        }
        # The 'sid' is not actually used by the server. We put it there
        #  so that we can identify what server a given song ID is
        #    playing on from the VLC stream. This is needed in order
        #      to properly implement get_now_playing()

        if password == "":
            self.secure_password = True
            self.password = password
        else:
            self.secure_password = False

            # Store the password hex encoded on disk
            if password[0:4] != "enc:":
                self.password = (b"enc:" + hexlify(bytes(password, encoding="utf8"))).decode('utf-8')
            else:
                self.password = password

        # Clean up the server address
        if server_url.count(".") == 0:
            server_url += ".subsonic.org"
        if server_url[0:7] != "http://" and server_url[0:8] != "https://":
            server_url = "https://" + server_url
        if server_url[-6:] != "/rest/":
            server_url = server_url + "/rest/"
        self.server_id = server_id
        self.server_url = server_url
        self.scrobble = scrobble
        self.server_name = server_name
        self.enabled = enabled

        if bitrate == "":
            self.bitrate = None
        else:
            self.bitrate = int(bitrate)

        self.online = False
        self.pickle_file = utils.get_home(self.server_name + ".pickle")
        self.library = pysonic.Library(server=self)

        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def generate_md5_password(self) -> None:
        """Creates a random salt and sets the md5(password+salt) and
        salt in the default args."""

        salt = utils.salt_generator()
        self.default_params['s'] = salt

        pwd = bytes.fromhex(self.password[4:]).decode('utf-8')
        to_hash = f"{pwd}{salt}".encode("ascii")
        self.default_params['t'] = hashlib.md5(to_hash).hexdigest()

    def pickle(self) -> None:
        """ Pickles the song library and writes it to disk. """

        # Don't save useless information in the pickle
        self.library.update_server(None)
        self.library.album_ids = None
        self.library.artist_ids = None
        self.library.song_ids = None
        self.library.prev_res = None

        # Dump the pickle
        pickle.dump(self.library, open(utils.get_home(".tmp.pickle"), "wb"), 2)
        os.rename(utils.get_home(".tmp.pickle"), self.pickle_file)

        # Re-set the server
        self.library.update_server(self)

    def print_config(self) -> str:
        """Return a string corresponding to the config file format
        for this server. """

        password = self.password
        if self.secure_password:
            password = ""
        print_bitrate = str(self.bitrate)
        if self.bitrate is None:
            print_bitrate = ""
        conf = f"""[{self.server_name}]
Host: {self.server_url}
Username: {self.default_params['u']}
Password: {password}
Bitrate: {print_bitrate}
Enabled: {str(self.enabled)}
Scrobble: {str(self.scrobble)}

"""
        return conf

    def __str__(self) -> str:
        return self.print_config()

    def sub_request(self,
                    page: str = "ping",
                    list_type: str = 'subsonic-response',
                    extras: dict = None,
                    timeout: int = 10,
                    return_root: bool = False) -> Union[List[Element], Element, str]:
        """Query subsonic, parse resulting xml and return either
         a list of Element objects, a stream URL if in stream mode,
         or the root element if return_root is True."""

        # Generate a unique salt for this request
        self.generate_md5_password()

        # Add request specific parameters to our hash
        if extras is None:
            extras = {}

        # Prepare the requests
        request = Request('GET', self.server_url.rstrip() + page.rstrip(), params={**self.default_params, **extras})
        prepped = self.session.prepare_request(request)

        # To stream we only want the URL returned, not the data
        if page == "stream":
            return prepped.url

        logging.debug(f'Request URL calculated as: {prepped.url}')

        # Get the server response
        try:
            r = self.session.send(prepped, timeout=timeout)
            r.raise_for_status()
        except requests.HTTPError:
            raise PysonicException("Request to subsonic server timed or failed three times in a row.")

        # Parse the XML
        root = ETree.fromstring(r.text)

        logging.debug(f'Got response from server. As text:\n{r.text}\n\nAs parsed XML:\n{root}')

        # Make sure the result is valid
        if root.attrib['status'] != 'ok':
            raise ValueError(f"Server responded with error: {root[0].attrib['message']}")

        # Short circuit return the whole tree if requested
        if return_root:
            return root

        # Return a list of the elements with the specified type
        return list(root.iter(tag='{http://subsonic.org/restapi}' + list_type))

    def go_online(self) -> None:
        """Ping the server to ensure it is online, if it is load the
        pickle or generate the local cache if necessary. """

        if self.password == "":
            self.password = (b"enc:" + hexlify(bytes(getpass.getpass(), encoding="utf8"))).decode('utf-8')

        sys.stdout.write(f"Checking if server {self.server_name} is online: ")
        sys.stdout.flush()

        # Don't add the server to our server list if it crashes out
        try:
            self.sub_request(timeout=2)
        except (PysonicException, ValueError):
            self.online = False
            return

        self.online = True
        sys.stdout.write('Yes\n')
        sys.stdout.flush()

        # Try to load the pickle, build the library if necessary
        need_new_build = False
        try:
            self.library = pickle.load(open(self.pickle_file, "rb"))
        except IOError:
            need_new_build = True
        except (EOFError, TypeError, AttributeError, pickle.UnpicklingError):
            print("Library archive corrupt or generated by old version of pysonic. Rebuilding library.")
            need_new_build = True

        if need_new_build:
            self.library = pysonic.Library(self)
            sys.stdout.write("Building library.")
            self.library.fill_artists()
            self.pickle()
            print("")

        # Update the server that the songs use
        self.library.update_server(self)
        # Update the library in the background
        if self.library.update_library() > 0:
            print("Saving new library.")
            self.pickle()

    def __repr__(self) -> str:
        return f"Server(server_url='{self.server_url}')"

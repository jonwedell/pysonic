import configparser
import os
import readline
import sys
from traceback import print_tb, print_exception

from filelock import FileLock, Timeout

import pysonic
import pysonic.commands as commands
import pysonic.utils as utils


class PysonicContext:
    def __init__(self, path: str = None):
        if path:
            pysonic.state.root_dir = path
        path = utils.get_home()
        # Make sure the .pysonic folder exists
        if not os.path.isdir(path):
            os.makedirs(path)
        self.lock = FileLock(utils.get_home('lock'), timeout=1)

    def __enter__(self):
        try:
            self.lock.acquire()
        except Timeout:
            print('It looks like pysonic is already running.')
            sys.exit(1)
        # Parse the config file, load (or query) the server data
        config = configparser.ConfigParser()
        config.read(utils.get_home("config"))
        for each_server in config.sections():

            try:
                scrobble_plays = config.getboolean(each_server, 'scrobble')
            except configparser.NoOptionError:
                scrobble_plays = False

            new_server = pysonic.Server(len(pysonic.state.all_servers), each_server,
                                        config.get(each_server, 'username'),
                                        config.get(each_server, 'password'),
                                        config.get(each_server, 'host'),
                                        enabled=config.getboolean(each_server, 'enabled'),
                                        bitrate=config.get(each_server, 'bitrate'),
                                        scrobble=scrobble_plays)
            pysonic.state.all_servers.append(new_server)

            if new_server.enabled:
                sys.stdout.write("Loading server " + new_server.server_name + ": ")
                sys.stdout.flush()
                new_server.go_online()
            else:
                print("Loading server " + new_server.server_name + ": Disabled.")

        # Create our list of active servers
        for each_server in pysonic.state.all_servers:
            if each_server.enabled and each_server.online:
                pysonic.state.enabled_servers.append(each_server)

        # No valid servers
        if len(pysonic.state.enabled_servers) < 1:
            if len(config.sections()) > 0:
                print("No connections established. Do you have at least one server "
                      f"specified in {utils.get_home('config')} and are your username, server "
                      "URL, and password correct?")
                sys.exit(10)
            else:
                print("No configuration file found. Configure a server now.")
                commands.add_server()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type != SystemExit and exc_type != KeyboardInterrupt:
            print("\n")
            print_exception(exc_type, tb=exc_tb, value=exc_val)
        print('\nShutting down...')
        # Create the history file if it doesn't exist
        if not os.path.isfile(utils.get_home("history")):
            open(utils.get_home("history"), "a").close()
        readline.write_history_file(utils.get_home("history"))

        # Write the current servers to the config file
        config_str = ""
        for one_server in pysonic.state.all_servers:
            config_str += one_server.print_config()
        open(utils.get_home("config"), 'w').write(config_str)
        self.lock.release()
        print('Goodbye!')
        return True

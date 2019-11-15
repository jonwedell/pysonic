import os
import platform
import socket
import subprocess
import telnetlib
import time

from pysonic.exceptions import PysonicException


class VLCInterface(object):
    """Allows for interfacing (or creating and then interfacing)
    with local VLC instance. """

    def __init__(self, player=None):
        try:
            self.telnet_con = telnetlib.Telnet("localhost", 4212, 3)
        except socket.error:
            # Use the player they specify
            if player:
                vlc_command = [player]

            # Try to figure out where the player is
            else:
                vlc_command = ["/usr/bin/vlc"]

                # If MacOS version exists
                if os.path.isfile("/Applications/VLC.app/Contents/MacOS/VLC"):
                    vlc_command = ["/Applications/VLC.app/Contents/MacOS/VLC"]

            # Make sure we have a valid VLC location
            if not os.path.isfile(vlc_command[0]):
                raise IOError(f"Did not find VLC binary at location: {player}")

            # Figure out the interactive argument
            if platform.system() == "Linux":
                vlc_command.append("-I")
            else:
                # Mac
                vlc_command.append("--intf")

            vlc_command.extend(["Telnet", "--telnet-password", "admin", "--no-loop", "--http-reconnect"])

            vlc_process = subprocess.Popen(vlc_command, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

            while vlc_process.poll() is None:
                # Try opening the connection again
                try:
                    self.telnet_con = telnetlib.Telnet("localhost", 4212)
                    break
                except socket.error:
                    time.sleep(.01)

            # The VLC process died or never opened
            else:
                raise PysonicException("Could not connect to launched VLC process.")

        # Do the login dance
        self.write("admin\n")
        self.read()
        # Make the VLC prompt match
        self.write("set prompt :\n")
        self.read()

    def read(self):
        """Read from the VLC socket. """

        try:
            # Make sure if they send a message they wait a bit
            #  before receiving
            time.sleep(.1)
            vlc_message = self.telnet_con.read_very_eager()
            read = vlc_message
            while len(read) > 0:
                read = self.telnet_con.read_very_eager()
                vlc_message += read
            if len(vlc_message) >= 3:
                vlc_message = vlc_message[:-3]
            elif len(vlc_message) == 1 and vlc_message == ":":
                vlc_message = ""
            return vlc_message.decode('utf-8')
        except (EOFError, socket.error):
            raise PysonicException("VLC socket died, please restart.")

    def write(self, message):
        """Write a command to the VLC socket. """

        try:
            if message[-1:] != "\n":
                message += "\n"
            self.telnet_con.write(message.encode('ascii'))
        except (EOFError, socket.error):
            raise PysonicException("VLC socket died, please restart.")

    def read_write(self, message):
        """Write a command and send back the response. """

        self.read()
        self.write(str(message))
        return self.read()

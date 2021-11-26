#!/usr/bin/env python3

"""
Jon Wedell

* THIS SOFTWARE IS PROVIDED ''AS IS'' AND ANY
* EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
* WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
* DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY
* DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
* (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
* LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
* ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
* (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
* SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import logging
import readline
import signal
from optparse import OptionParser

import pysonic
import pysonic.utils as utils
from pysonic.cmd import PysonicShell
from pysonic.context import PysonicContext

########################################################################
#              Methods and classes above, code below                   #
########################################################################

signal.signal(signal.SIGWINCH, utils.update_width)

# Specify some basic information about our command
parser = OptionParser(usage="usage: %prog", version="%prog 1", description="Play songs from subsonic.")
parser.add_option("--verbose", action="store_true", dest="verbose", default=False,
                  help="Enable verbose mode")
parser.add_option("--vlc-location", action="store", dest="player", default=None, help="Location of VLC binary.")
parser.add_option("--config-path", '-c', action="store", dest="path", default=None,
                  help="Use the specified directory for configuration and library files")

# pysonic.options, parse 'em
(pysonic.options, cmd_input) = parser.parse_args()

# Set the appropriate log level
if pysonic.options.verbose:
    logging.basicConfig(format='%(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                        level=logging.DEBUG)
else:
    logging.basicConfig(format='%(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                        level=logging.INFO)
if pysonic.options.path:
    pysonic.state.root_dir = pysonic.options.path

with PysonicContext():
    # Connect to the VLC interface
    pysonic.state.vlc = pysonic.VLCInterface()

    # Load previous command history
    try:
        readline.read_history_file(utils.get_home("history"))
    except IOError:
        pass

    PysonicShell().cmdloop()

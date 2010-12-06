#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free  Software Foundation; either version 2 of the License, or
# (at your option)  any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA.

import logging
import os
import virtinst

import utils

# Force is_blktap_capable to return a consistent value, so test suite
# won't change based on the system
virtinst._util.is_blktap_capable = lambda: False

# Setup logging
rootLogger = logging.getLogger()
for handler in rootLogger.handlers:
    rootLogger.removeHandler(handler)

logging.basicConfig(level=logging.DEBUG,
                    format="%(levelname)-8s %(message)s")

if utils.get_debug():
    rootLogger.setLevel(logging.DEBUG)
else:
    rootLogger.setLevel(logging.ERROR)

# Used to ensure consistent SDL xml output
os.environ["HOME"] = "/tmp"
os.environ["DISPLAY"] = ":3.4"


# Have imports down here so they get the benefit of logging setup etc.
import capabilities
import validation
import xmlconfig
import image
import storage
import urltest
import clonetest
import nodedev
import virtconvtest
import interface
import xmlparse

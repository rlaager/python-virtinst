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

import libvirt
import difflib
import logging
import os, sys
import virtinst

# Force is_blktap_capable to return a consistent value, so test suite
# won't change based on the system
virtinst._util.is_blktap_capable = lambda: False

# Setup logging
rootLogger = logging.getLogger()
for handler in rootLogger.handlers:
    rootLogger.removeHandler(handler)

logging.basicConfig(level=logging.DEBUG,
                    format="%(levelname)-8s %(message)s")

if os.environ.has_key("DEBUG_TESTS") and os.environ["DEBUG_TESTS"] == "1":
    rootLogger.setLevel(logging.DEBUG)
    debug = True
else:
    rootLogger.setLevel(logging.ERROR)
    debug = False

# Used to ensure consistent SDL xml output
os.environ["HOME"] = "/tmp"
os.environ["DISPLAY"] = ":3.4"

def open_testdriver():
    return libvirt.open("test:///%s/tests/testdriver.xml" % os.getcwd())

# Register libvirt handler
def libvirt_callback(ignore, err):
    logging.warn("libvirt errmsg: %s" % err[2])
libvirt.registerErrorHandler(f=libvirt_callback, ctx=None)

def read_file(filename):
    """Helper function to read a files contents and return them"""
    f = open(filename, "r")
    out = f.read()
    f.close()

    return out

def diff_compare(actual_out, filename, expect_out=None):
    """Compare passed string output to contents of filename"""
    if not expect_out:
        expect_out = read_file(filename)

    diff = "".join(difflib.unified_diff(expect_out.splitlines(1),
                                        actual_out.splitlines(1),
                                        fromfile=filename,
                                        tofile="Generated Output"))
    if diff:
        raise AssertionError("Conversion outputs did not match.\n%s" % diff)

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

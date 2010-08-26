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

import unittest
import glob
import traceback

import virtinst

import tests

conn = tests.open_testdriver()
def sanitize_file_xml(xml):
    # s/"/'/g from generated XML, matches what libxml dumps out
    # This won't work all the time, but should be good enough for testing
    return xml.replace("'", "\"")

class RoundTripTest(unittest.TestCase):

    def _compare(self, filename):
        expectXML = sanitize_file_xml(file(filename).read())
        guest = virtinst.Guest(connection=conn, parsexml=expectXML)
        actualXML = guest.get_config_xml()
        tests.diff_compare(actualXML, expect_out=expectXML)

    def testRoundTrip(self):
        exclude = ["misc-xml-escaping.xml"]
        failed = False
        error = ""
        for f in glob.glob("tests/xmlconfig-xml/*.xml"):
            if filter(f.endswith, exclude):
                continue

            try:
                self._compare(f)
            except Exception:
                failed = True
                error += "%s:\n%s\n" % (f, "".join(traceback.format_exc()))

        if failed:
            raise AssertionError("Roundtrip parse tests failed:\n%s" % error)


if __name__ == "__main__":
    unittest.main()

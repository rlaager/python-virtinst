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

class XMLParseTest(unittest.TestCase):

    def _roundtrip_compare(self, filename):
        expectXML = sanitize_file_xml(file(filename).read())
        guest = virtinst.Guest(connection=conn, parsexml=expectXML)
        actualXML = guest.get_config_xml()
        tests.diff_compare(actualXML, expect_out=expectXML)

    def _alter_compare(self, actualXML, outfile):
        tests.test_create(conn, actualXML)
        tests.diff_compare(actualXML, outfile)

    def testRoundTrip(self):
        """
        Make sure parsing doesn't output different XML
        """
        exclude = ["misc-xml-escaping.xml"]
        failed = False
        error = ""
        for f in glob.glob("tests/xmlconfig-xml/*.xml"):
            if filter(f.endswith, exclude):
                continue

            try:
                self._roundtrip_compare(f)
            except Exception:
                failed = True
                error += "%s:\n%s\n" % (f, "".join(traceback.format_exc()))

        if failed:
            raise AssertionError("Roundtrip parse tests failed:\n%s" % error)

    def _set_and_check(self, obj, param, initval, newval):
        """
        Check expected initial value obj.param == initval, then
        set newval, and make sure it is returned properly
        """
        curval = getattr(obj, param)
        self.assertEquals(initval, curval)

        setattr(obj, param, newval)
        curval = getattr(obj, param)
        self.assertEquals(newval, curval)

    def testAlterGuest(self):
        """
        Test changing Guest() parameters after parsing
        """
        infile  = "tests/xmlparse-xml/change-guest-in.xml"
        outfile = "tests/xmlparse-xml/change-guest-out.xml"
        guest = virtinst.Guest(connection=conn,
                               parsexml=file(infile).read())

        check = lambda x, y, z: self._set_and_check(guest, x, y, z)

        check("name", "TestGuest", "change_name")
        check("description", None, "Hey desc changed")
        check("vcpus", 5, 28)
        check("cpuset", "1-3", "1-5,15")
        check("maxmemory", 400, 500)
        check("memory", 200, 1000)
        check("maxmemory", 1000, 2000)
        check("uuid", "12345678-1234-1234-1234-123456789012",
                      "11111111-2222-3333-4444-555555555555")

        self._alter_compare(guest.get_config_xml(), outfile)

    def testAlterDisk(self):
        """
        Test changing VirtualDisk() parameters after parsing
        """
        infile  = "tests/xmlparse-xml/change-disk-in.xml"
        outfile = "tests/xmlparse-xml/change-disk-out.xml"
        guest = virtinst.Guest(connection=conn,
                               parsexml=file(infile).read())

        # XXX: Set size up front. VirtualDisk validation is kind of
        # convoluted. If trying to change a non-existing one and size wasn't
        # already specified, we will error out.
        disk1 = guest.disks[0]
        disk1.size = 1
        disk2 = guest.disks[2]
        disk2.size = 1
        disk3 = guest.disks[5]
        disk3.size = 1

        check = lambda x, y, z: self._set_and_check(disk1, x, y, z)
        check("path", "/tmp/test.img", "/dev/loop0")
        check("driver_name", None, "test")
        check("driver_type", None, "foobar")

        check = lambda x, y, z: self._set_and_check(disk2, x, y, z)
        check("path", "/dev/loop0", None)
        check("device", "cdrom", "floppy")
        check("read_only", True, False)
        check("target", None, "fde")
        check("bus", None, "fdc")

        check = lambda x, y, z: self._set_and_check(disk3, x, y, z)
        check("path", None, "/default-pool/default-vol")
        check("shareable", False, True)
        check("driver_cache", None, "writeback")

        self._alter_compare(guest.get_config_xml(), outfile)

    def testSingleDisk(self):
        xml = ("""<disk type="file" device="disk"><source file="/a.img"/>"""
               """<target dev="hda" bus="ide"/></disk>""")
        d = virtinst.VirtualDisk(parsexml=xml)
        self._set_and_check(d, "target", "hda", "hdb")
        self.assertEquals(xml.replace("hda", "hdb"), d.get_xml_config())

    def testAlterChars(self):
        infile  = "tests/xmlparse-xml/change-chars-in.xml"
        outfile = "tests/xmlparse-xml/change-chars-out.xml"
        guest = virtinst.Guest(connection=conn,
                               parsexml=file(infile).read())

        self._alter_compare(guest.get_config_xml(), outfile)

    def testAlterControllers(self):
        infile  = "tests/xmlparse-xml/change-controllers-in.xml"
        outfile = "tests/xmlparse-xml/change-controllers-out.xml"
        guest = virtinst.Guest(connection=conn,
                               parsexml=file(infile).read())

        self._alter_compare(guest.get_config_xml(), outfile)

    def testAlterNics(self):
        infile  = "tests/xmlparse-xml/change-nics-in.xml"
        outfile = "tests/xmlparse-xml/change-nics-out.xml"
        guest = virtinst.Guest(connection=conn,
                               parsexml=file(infile).read())

        self._alter_compare(guest.get_config_xml(), outfile)

    def testAlterInputs(self):
        infile  = "tests/xmlparse-xml/change-inputs-in.xml"
        outfile = "tests/xmlparse-xml/change-inputs-out.xml"
        guest = virtinst.Guest(connection=conn,
                               parsexml=file(infile).read())

        self._alter_compare(guest.get_config_xml(), outfile)

    def testAlterGraphics(self):
        infile  = "tests/xmlparse-xml/change-graphics-in.xml"
        outfile = "tests/xmlparse-xml/change-graphics-out.xml"
        guest = virtinst.Guest(connection=conn,
                               parsexml=file(infile).read())

        self._alter_compare(guest.get_config_xml(), outfile)

    def testAlterVideos(self):
        infile  = "tests/xmlparse-xml/change-videos-in.xml"
        outfile = "tests/xmlparse-xml/change-videos-out.xml"
        guest = virtinst.Guest(connection=conn,
                               parsexml=file(infile).read())

        self._alter_compare(guest.get_config_xml(), outfile)

    def testAlterHostdevs(self):
        infile  = "tests/xmlparse-xml/change-hostdevs-in.xml"
        outfile = "tests/xmlparse-xml/change-hostdevs-out.xml"
        guest = virtinst.Guest(connection=conn,
                               parsexml=file(infile).read())

        self._alter_compare(guest.get_config_xml(), outfile)

    def testAlterWatchdogs(self):
        infile  = "tests/xmlparse-xml/change-watchdogs-in.xml"
        outfile = "tests/xmlparse-xml/change-watchdogs-out.xml"
        guest = virtinst.Guest(connection=conn,
                               parsexml=file(infile).read())

        self._alter_compare(guest.get_config_xml(), outfile)

    def testAlterSounds(self):
        infile  = "tests/xmlparse-xml/change-sounds-in.xml"
        outfile = "tests/xmlparse-xml/change-sounds-out.xml"
        guest = virtinst.Guest(connection=conn,
                               parsexml=file(infile).read())

        self._alter_compare(guest.get_config_xml(), outfile)

if __name__ == "__main__":
    unittest.main()

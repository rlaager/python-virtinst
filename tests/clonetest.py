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
import os, os.path
import tests
import libvirt

from virtinst import CloneManager
CloneDesign = CloneManager.CloneDesign

ORIG_NAME  = "clone-orig"
CLONE_NAME = "clone-new"

clonexml_dir = os.path.join(os.getcwd(), "tests/clone-xml")
clone_files = []

for f in os.listdir(clonexml_dir):
    if f.endswith("-out.xml"):
        f = f[0:(len(f) - len("-out.xml"))]
        if f not in clone_files:
            clone_files.append(f)

conn = libvirt.open("test:///default")

def fake_is_uri_remote(ignore):
    return True

class TestClone(unittest.TestCase):

    def setUp(self):
        pass

    def _clone_helper(self, filebase, disks=None):
        """Helper for comparing clone input/output from 2 xml files"""
        infile = os.path.join(clonexml_dir, filebase + "-in.xml")
        in_content = tests.read_file(infile)

        cloneobj = CloneDesign(connection=conn)
        cloneobj.original_xml = in_content

        cloneobj = self._default_clone_values(cloneobj, disks)
        self._clone_compare(cloneobj, filebase)
        self._clone_define(filebase)

    def _default_clone_values(self, cloneobj, disks=None):
        """Sets default values for the cloned VM."""
        cloneobj.clone_name = "clone-new"
        cloneobj.clone_uuid = "12345678-1234-1234-1234-123456789012"

        cloneobj.clone_mac = "01:23:45:67:89:00"
        cloneobj.clone_mac = "01:23:45:67:89:01"

        if disks != None:
            for disk in disks:
                cloneobj.clone_devices = disk
        else:
            cloneobj.clone_devices = "/tmp/clone1.img"
            cloneobj.clone_devices = "/tmp/clone2.img"
            cloneobj.clone_devices = "/tmp/clone3.img"
            cloneobj.clone_devices = "/tmp/clone4.img"
            cloneobj.clone_devices = "/tmp/clone5.img"

        return cloneobj

    def _clone_compare(self, cloneobj, outbase):
        """Helps compare output from passed clone instance with an xml file"""
        outfile = os.path.join(clonexml_dir, outbase + "-out.xml")

        cloneobj.setup()

        tests.diff_compare(cloneobj.clone_xml, outfile)

    def _clone_define(self, filebase):
        """Take the valid output xml and attempt to define it on the
           connection to ensure we don't get any errors"""
        outfile = os.path.join(clonexml_dir, filebase + "-out.xml")
        outxml = tests.read_file(outfile)

        vm = None
        try:
            vm = conn.defineXML(outxml)
        finally:
            if vm:
                vm.undefine()

    def testCloneGuestLookup(self):
        """Test using a vm name lookup for cloning"""
        for base in clone_files:
            infile = os.path.join(clonexml_dir, base + "-in.xml")

            vm = None
            try:
                conn.defineXML(tests.read_file(infile))

                cloneobj = CloneDesign(connection=conn)
                cloneobj.original_guest = ORIG_NAME

                cloneobj = self._default_clone_values(cloneobj)
                self._clone_compare(cloneobj, base)
            finally:
                if vm:
                    vm.undefine()

    def testCloneFromFile(self):
        """Test using files for input and output"""
        for base in clone_files:
            self._clone_helper(base)

    def testRemoteNoStorage(self):
        """Test remote clone where VM has no storage that needs cloning"""
        oldfunc = CloneManager._util.is_uri_remote
        try:
            CloneManager._util.is_uri_remote = fake_is_uri_remote

            for base in [ "nostorage", "noclone-storage" ] :
                self._clone_helper(base, disks=[])

        finally:
            CloneManager._util.is_uri_remote = oldfunc

    def testRemoteWithStorage(self):
        """
        Test remote clone with storage needing cloning. Should fail,
        since libvirt has no storage clone api.
        """
        oldfunc = CloneManager._util.is_uri_remote
        try:
            CloneManager._util.is_uri_remote = fake_is_uri_remote

            for base in [ "general-cfg" ] :
                try:
                    self._clone_helper(base, disks=["/default-pool/1.img",
                                                    "/default-pool/2.img" ])

                    # We shouldn't succeed, so test fails
                    raise AssertionError("Remote clone with storage passed "
                                         "when it shouldn't.")
                except (ValueError, RuntimeError):
                    # Exception expected
                    pass
        finally:
            CloneManager._util.is_uri_remote = oldfunc


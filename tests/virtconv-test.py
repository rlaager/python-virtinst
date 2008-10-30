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
import difflib
import string
import virtinst
import virtconv
import os, os.path, glob
import libvirt
import urlgrabber.progress as progress

vmx2virtimage_dir = "tests/virtconv-files/vmx2virtimage"
vmx2virtimage_files = [ "test" ]

virtimage2vmx_dir = "tests/virtconv-files/virtimage2vmx"
virtimage2vmx_files = [ "image" ]

# For x2x conversion, we want to use already tested output, since ideally
# we should be able to run a generated config continually through the
# converter and it will generate the same result
vmx2vmx_dirs = [ virtimage2vmx_dir ]
virtimage2virtimage_dirs = [ vmx2virtimage_dir ]

class TestVirtConv(unittest.TestCase):

    def setUp(self):
        pass

    def _compare(self, actual_out, file):
        f = open(file, "r")
        expect_out = string.join(f.readlines(), "")
        f.close()

        diff = "".join(difflib.unified_diff(expect_out.splitlines(1),
                                            actual_out.splitlines(1),
                                            fromfile=file,
                                            tofile="Generated Output"))
        if diff:
            raise AssertionError("Conversion outputs did not match.\n"
                                 "%s" % diff)
        else:
            self.assertTrue(True)

    def _convert_helper(self, dir, filebase, input_type, output_type):
        infile  = os.path.join(dir, filebase + "." + input_type)
        outfile = os.path.join(dir, filebase + "." + output_type)

        inp  = virtconv.formats.find_parser_by_file(infile)
        outp = virtconv.formats.parser_by_name(output_type)

        if not inp or inp.name != input_type:
            raise AssertionError("find_parser_by_file for '%s' returned "
                                 "wrong parser type.\n"
                                 "Expected: %s\n"
                                 "Received: %s\n" % \
                                 (infile, input_type,
                                 str((not inp) and str(inp) or inp.name)))

        vmdef = inp.import_file(infile)
        out_expect = outp.export(vmdef)
        self._compare(out_expect, outfile)

    def testVMX2VirtImage(self):
        for filename in vmx2virtimage_files:
            self._convert_helper(vmx2virtimage_dir, filename,
                                 "vmx", "virt-image")

    def testVMX2VMX(self):
        for dir in vmx2vmx_dirs:
            for filepath in glob.glob(os.path.join(dir, "*.vmx")):
                filename = os.path.splitext(os.path.basename(filepath))[0]
                self._convert_helper(dir, filename, "vmx", "vmx")

    def testVirtImage2VMX(self):
        for filename in virtimage2vmx_files:
            self._convert_helper(virtimage2vmx_dir, filename,
                                 "virt-image", "vmx")

    def testVirtImage2VirtImage(self):
        for dir in virtimage2virtimage_dirs:
            for filepath in glob.glob(os.path.join(dir, "*.virt-image")):
                filename = os.path.splitext(os.path.basename(filepath))[0]
                self._convert_helper(dir, filename, "virt-image", "virt-image")


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
import virtinst
import virtinst.ImageParser
import os

import tests
import xmlconfig

class TestImageParser(unittest.TestCase):

    def testImageParsing(self):
        f = open(os.path.join("tests/image-xml", "image.xml"), "r")
        xml = f.read()
        f.close()

        img = virtinst.ImageParser.parse(xml, ".")
        self.assertEqual("test-image", img.name)
        self.assertTrue(img.domain)
        self.assertEqual(5, len(img.storage))
        self.assertEqual(2, len(img.domain.boots))
        self.assertEqual(1, img.domain.interface)
        boot = img.domain.boots[0]
        self.assertEqual("xvdb", boot.drives[1].target)

    def testMultipleNics(self):
        f = open(os.path.join("tests/image-xml", "image2nics.xml"), "r")
        xml = f.read()
        f.close()

        img = virtinst.ImageParser.parse(xml, ".")
        self.assertEqual(2, img.domain.interface)


    # Build libvirt XML from the image xml
    # XXX: This doesn't set up devices, so the guest xml will be pretty
    # XXX: sparse. There should really be a helper in the Image classes
    # XXX: that turns virt-image xml into a minimal Guest object, but
    # XXX: maybe that's just falling into the realm of virt-convert
    def testImage2XML(self):
        basedir = "tests/image-xml/"
        image2guestdir = basedir + "image2guest/"
        image = virtinst.ImageParser.parse_file(basedir + "image.xml")

        # ( boot index from virt-image xml, filename to compare against)
        matrix = [ (0, "image-xenpv32.xml"),
                   (1, "image-xenfv32.xml") ]

        g = xmlconfig.get_basic_paravirt_guest()
        caps = virtinst.CapabilitiesParser.parse(g.conn.getCapabilities())
        for idx, fname in matrix:
            inst = virtinst.ImageInstaller(image, caps, boot_index=idx)

            if inst.is_hvm():
                g = xmlconfig.get_basic_fullyvirt_guest()
            else:
                g = xmlconfig.get_basic_paravirt_guest()

            g.installer = inst
            tests.diff_compare(g.get_config_xml(install=True),
                               image2guestdir + fname)

if __name__ == "__main__":
    unittest.main()

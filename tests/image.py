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

class TestImageParser(unittest.TestCase):

    def testImageParsing(self):
        file = open(os.path.join("tests", "image.xml"), "r")
        xml = file.read()
        file.close()

        img = virtinst.ImageParser.parse(xml, ".")
        self.assertEqual("test-image", img.name)
        self.assertTrue(img.domain)
        self.assertEqual(5, len(img.storage))
        self.assertEqual(2, len(img.domain.boots))
        self.assertEqual(1, img.domain.interface)
        boot = img.domain.boots[0]
        self.assertEqual("xvdb", boot.drives[1].target)

    def testMultipleNics(self):
        file = open(os.path.join("tests", "image2nics.xml"), "r")
        xml = file.read()
        file.close()

        img = virtinst.ImageParser.parse(xml, ".")
        self.assertEqual(2, img.domain.interface)
if __name__ == "__main__":
    unittest.main()

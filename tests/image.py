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
        boot = img.domain.boots[0]
        self.assertEqual("xvdb", boot.disks[1].target)
if __name__ == "__main__":
    unittest.main()

import string
import unittest
import xeninst
import os

class TestXMLConfig(unittest.TestCase):

    def _compare(self, xenguest, filebase):
        f = open(filebase + ".xml", "r")
        expectXML = string.join(f.readlines(), "")
        f.close()

        actualXML = xenguest._get_config_xml()

        if os.environ.has_key("DEBUG_TESTS") and os.environ["DEBUG_TESTS"] == "xml":
            print "Actual: %d bytes '%s'" % (len(actualXML),  actualXML)
            print "Expect: %d bytes '%s'" % (len(expectXML),  expectXML)

        self.assertEqual(actualXML, expectXML)

    def _get_basic_paravirt_guest(self):
        g = xeninst.ParaVirtGuest(hypervisorURI="test:///default")
        g.name = "TestGuest"
        g.memory = int(200)
        g.uuid = "123456-1234-1234-1234-123456"
        g.kernel = "/boot/vmlinuz"
        g.initrd = "/boot/initrd"
        g.vcpus = 5
        return g

    def _get_basic_fullyvirt_guest(self):
        g = xeninst.FullVirtGuest(hypervisorURI="test:///default")
        g.name = "TestGuest"
        g.memory = int(200)
        g.uuid = "123456-1234-1234-1234-123456"
        g.cdrom = "/dev/cdrom"
        g.vcpus = 5
        return g

    def testParavirtDiskFile(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(xeninst.XenDisk("/xen/test.img", type=xeninst.XenDisk.TYPE_FILE))
        self._compare(g, "data-paravirt-disk-file")

    def testParavirtDiskBlock(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(xeninst.XenDisk("/dev/hdb1", type=xeninst.XenDisk.TYPE_BLOCK))
        self._compare(g, "data-paravirt-disk-block")

    def testParavirtDiskDrvPhy(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(xeninst.XenDisk("/dev/hdb1", type=xeninst.XenDisk.TYPE_BLOCK, \
                                       driverName = xeninst.XenDisk.DRIVER_PHY))
        self._compare(g, "data-paravirt-disk-drv-phy")

    def testParavirtDiskDrvFile(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(xeninst.XenDisk("/xen/test.img", type=xeninst.XenDisk.TYPE_FILE, \
                                       driverName = xeninst.XenDisk.DRIVER_FILE))
        self._compare(g, "data-paravirt-disk-drv-file")

    def testParavirtDiskDrvTap(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(xeninst.XenDisk("/xen/test.img", type=xeninst.XenDisk.TYPE_FILE, \
                                       driverName = xeninst.XenDisk.DRIVER_TAP))
        self._compare(g, "data-paravirt-disk-drv-tap")

    def testParavirtDiskDrvTapQCow(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(xeninst.XenDisk("/xen/test.img", type=xeninst.XenDisk.TYPE_FILE, \
                                       driverName = xeninst.XenDisk.DRIVER_TAP, \
                                       driverType = xeninst.XenDisk.DRIVER_TAP_QCOW))
        self._compare(g, "data-paravirt-disk-drv-tap-qcow")

    def testParavirtManyDisks(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(xeninst.XenDisk("/xen/test1.img", type=xeninst.XenDisk.TYPE_FILE))
        g.disks.append(xeninst.XenDisk("/xen/test2.img", type=xeninst.XenDisk.TYPE_FILE, \
                                       driverName = xeninst.XenDisk.DRIVER_TAP, \
                                       driverType = xeninst.XenDisk.DRIVER_TAP_QCOW))
        g.disks.append(xeninst.XenDisk("/dev/hdb1", type=xeninst.XenDisk.TYPE_BLOCK))
        self._compare(g, "data-paravirt-many-disks")

    def testFullyvirtDiskFile(self):
        g = self._get_basic_fullyvirt_guest()
        g.disks.append(xeninst.XenDisk("/xen/test.img", type=xeninst.XenDisk.TYPE_FILE))
        self._compare(g, "data-fullyvirt-disk-file")

    def testFullyvirtDiskBlock(self):
        g = self._get_basic_fullyvirt_guest()
        g.disks.append(xeninst.XenDisk("/dev/hdb1", type=xeninst.XenDisk.TYPE_BLOCK))
        self._compare(g, "data-fullyvirt-disk-block")


if __name__ == "__main__":
    unittest.main()
    

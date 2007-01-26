import string
import unittest
import virtinst
import os

class TestXMLConfig(unittest.TestCase):

    def _compare(self, xenguest, filebase, install):
        f = open("tests/" + filebase + ".xml", "r")
        expectXML = string.join(f.readlines(), "")
        f.close()

        actualXML = xenguest.get_config_xml(install=install)

        if os.environ.has_key("DEBUG_TESTS") and os.environ["DEBUG_TESTS"] == "xml":
            print "Actual: %d bytes '%s'" % (len(actualXML),  actualXML)
            print "Expect: %d bytes '%s'" % (len(expectXML),  expectXML)

        self.assertEqual(actualXML, expectXML)

    def _get_basic_paravirt_guest(self):
        g = virtinst.ParaVirtGuest(hypervisorURI="test:///default", type="xen")
        g.name = "TestGuest"
        g.memory = int(200)
        g.uuid = "123456-1234-1234-1234-123456"
        g.kernel = "/boot/vmlinuz"
        g.initrd = "/boot/initrd"
        g.vcpus = 5
        return g

    def _get_basic_fullyvirt_guest(self):
        g = virtinst.FullVirtGuest(hypervisorURI="test:///default", type="xen",
                                   emulator="/usr/lib/xen/bin/qemu-dm")
        g.name = "TestGuest"
        g.memory = int(200)
        g.uuid = "123456-1234-1234-1234-123456"
        g.cdrom = "/dev/cdrom"
        g.vcpus = 5
        return g

    def testBootParavirtDiskFile(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test.img", type=virtinst.VirtualDisk.TYPE_FILE))
        self._compare(g, "boot-paravirt-disk-file", False)

    def testBootParavirtDiskBlock(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/dev/hdb1", type=virtinst.VirtualDisk.TYPE_BLOCK))
        self._compare(g, "boot-paravirt-disk-block", False)

    def testBootParavirtDiskDrvPhy(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/dev/hdb1", type=virtinst.VirtualDisk.TYPE_BLOCK, \
                                       driverName = virtinst.VirtualDisk.DRIVER_PHY))
        self._compare(g, "boot-paravirt-disk-drv-phy", False)

    def testBootParavirtDiskDrvFile(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test.img", type=virtinst.VirtualDisk.TYPE_FILE, \
                                       driverName = virtinst.VirtualDisk.DRIVER_FILE))
        self._compare(g, "boot-paravirt-disk-drv-file", False)

    def testBootParavirtDiskDrvTap(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test.img", type=virtinst.VirtualDisk.TYPE_FILE, \
                                       driverName = virtinst.VirtualDisk.DRIVER_TAP))
        self._compare(g, "boot-paravirt-disk-drv-tap", False)

    def testBootParavirtDiskDrvTapQCow(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test.img", type=virtinst.VirtualDisk.TYPE_FILE, \
                                       driverName = virtinst.VirtualDisk.DRIVER_TAP, \
                                       driverType = virtinst.VirtualDisk.DRIVER_TAP_QCOW))
        self._compare(g, "boot-paravirt-disk-drv-tap-qcow", False)

    def testBootParavirtManyDisks(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test1.img", type=virtinst.VirtualDisk.TYPE_FILE))
        g.disks.append(virtinst.VirtualDisk("/xen/test2.img", type=virtinst.VirtualDisk.TYPE_FILE, \
                                       driverName = virtinst.VirtualDisk.DRIVER_TAP, \
                                       driverType = virtinst.VirtualDisk.DRIVER_TAP_QCOW))
        g.disks.append(virtinst.VirtualDisk("/dev/hdb1", type=virtinst.VirtualDisk.TYPE_BLOCK))
        self._compare(g, "boot-paravirt-many-disks", False)

    def testBootFullyvirtDiskFile(self):
        g = self._get_basic_fullyvirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test.img", type=virtinst.VirtualDisk.TYPE_FILE))
        self._compare(g, "boot-fullyvirt-disk-file", False)

    def testBootFullyvirtDiskBlock(self):
        g = self._get_basic_fullyvirt_guest()
        g.disks.append(virtinst.VirtualDisk("/dev/hdb1", type=virtinst.VirtualDisk.TYPE_BLOCK))
        self._compare(g, "boot-fullyvirt-disk-block", False)




    def testInstallParavirtDiskFile(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test.img", type=virtinst.VirtualDisk.TYPE_FILE))
        self._compare(g, "install-paravirt-disk-file", True)

    def testInstallParavirtDiskBlock(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/dev/hdb1", type=virtinst.VirtualDisk.TYPE_BLOCK))
        self._compare(g, "install-paravirt-disk-block", True)

    def testInstallParavirtDiskDrvPhy(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/dev/hdb1", type=virtinst.VirtualDisk.TYPE_BLOCK, \
                                       driverName = virtinst.VirtualDisk.DRIVER_PHY))
        self._compare(g, "install-paravirt-disk-drv-phy", True)

    def testInstallParavirtDiskDrvFile(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test.img", type=virtinst.VirtualDisk.TYPE_FILE, \
                                       driverName = virtinst.VirtualDisk.DRIVER_FILE))
        self._compare(g, "install-paravirt-disk-drv-file", True)

    def testInstallParavirtDiskDrvTap(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test.img", type=virtinst.VirtualDisk.TYPE_FILE, \
                                       driverName = virtinst.VirtualDisk.DRIVER_TAP))
        self._compare(g, "install-paravirt-disk-drv-tap", True)

    def testInstallParavirtDiskDrvTapQCow(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test.img", type=virtinst.VirtualDisk.TYPE_FILE, \
                                       driverName = virtinst.VirtualDisk.DRIVER_TAP, \
                                       driverType = virtinst.VirtualDisk.DRIVER_TAP_QCOW))
        self._compare(g, "install-paravirt-disk-drv-tap-qcow", True)

    def testInstallParavirtManyDisks(self):
        g = self._get_basic_paravirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test1.img", type=virtinst.VirtualDisk.TYPE_FILE))
        g.disks.append(virtinst.VirtualDisk("/xen/test2.img", type=virtinst.VirtualDisk.TYPE_FILE, \
                                       driverName = virtinst.VirtualDisk.DRIVER_TAP, \
                                       driverType = virtinst.VirtualDisk.DRIVER_TAP_QCOW))
        g.disks.append(virtinst.VirtualDisk("/dev/hdb1", type=virtinst.VirtualDisk.TYPE_BLOCK))
        self._compare(g, "install-paravirt-many-disks", True)

    def testInstallFullyvirtDiskFile(self):
        g = self._get_basic_fullyvirt_guest()
        g.disks.append(virtinst.VirtualDisk("/xen/test.img", type=virtinst.VirtualDisk.TYPE_FILE))
        self._compare(g, "install-fullyvirt-disk-file", True)

    def testInstallFullyvirtDiskBlock(self):
        g = self._get_basic_fullyvirt_guest()
        g.disks.append(virtinst.VirtualDisk("/dev/hdb1", type=virtinst.VirtualDisk.TYPE_BLOCK))
        self._compare(g, "install-fullyvirt-disk-block", True)



if __name__ == "__main__":
    unittest.main()
    

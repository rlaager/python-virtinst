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
import os
import libvirt
import urlgrabber.progress as progress
import logging

import virtinst
from virtinst import VirtualDisk
import tests

conn = libvirt.open("test:///default")

def get_basic_paravirt_guest():
    g = virtinst.ParaVirtGuest(connection=conn, type="xen")
    g.name = "TestGuest"
    g.memory = int(200)
    g.maxmemory = int(400)
    g.uuid = "12345678-1234-1234-1234-123456789012"
    g.boot = ["/boot/vmlinuz","/boot/initrd"]
    g.graphics = (True, "vnc", None, "ja")
    g.vcpus = 5
    return g

conn = libvirt.open("test:///default")
def get_basic_fullyvirt_guest():
    g = virtinst.FullVirtGuest(connection=conn, type="xen",
                               emulator="/usr/lib/xen/bin/qemu-dm",
                               arch="i686")
    g.name = "TestGuest"
    g.memory = int(200)
    g.maxmemory = int(400)
    g.uuid = "12345678-1234-1234-1234-123456789012"
    g.cdrom = "/dev/loop0"
    g.set_os_type("other")
    g.set_os_variant("generic")
    g.graphics = (True, "sdl")
    g.features['pae'] = 0
    g.vcpus = 5
    return g

def get_filedisk(path="/tmp/test.img"):
    return VirtualDisk(path, size=.0001, conn=conn)

def get_blkdisk():
    return VirtualDisk("/dev/loop0", conn=conn)

class TestXMLConfig(unittest.TestCase):

    def _compare(self, xenguest, filebase, install):
        filename = os.path.join("tests/xmlconfig-xml", filebase + ".xml")
        xenguest._prepare_install(progress.BaseMeter())
        try:
            actualXML = xenguest.get_config_xml(install=install)
            tests.diff_compare(actualXML, filename)

            try:
                # Should probably break this out into a separate function
                dom = xenguest.conn.defineXML(actualXML)
                dom.create()
                dom.destroy()
                dom.undefine()
            except Exception, e:
                # Libvirt throws errors since we are defining domain
                # type='xen', when test driver can only handle type='test'
                # Would be nice to turn this back on, but it we need a
                # maintainable solution that still tests the important
                # virtinst code paths.
                logging.debug("Defining xmlconfig failed. Error is: %s"
                              "\nXML is:\n%s" % (str(e), actualXML))
        finally:
            xenguest.installer.cleanup()


    def testBootParavirtDiskFile(self):
        g = get_basic_paravirt_guest()
        g.disks.append(get_filedisk())
        self._compare(g, "boot-paravirt-disk-file", False)

    def testBootParavirtDiskBlock(self):
        g = get_basic_paravirt_guest()
        g.disks.append(get_blkdisk())
        self._compare(g, "boot-paravirt-disk-block", False)

    def testBootParavirtDiskDrvPhy(self):
        g = get_basic_paravirt_guest()
        disk = get_blkdisk()
        disk.driver_name = VirtualDisk.DRIVER_PHY
        g.disks.append(disk)
        self._compare(g, "boot-paravirt-disk-drv-phy", False)

    def testBootParavirtDiskDrvFile(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_FILE
        g.disks.append(disk)
        self._compare(g, "boot-paravirt-disk-drv-file", False)

    def testBootParavirtDiskDrvTap(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_TAP
        g.disks.append(disk)
        self._compare(g, "boot-paravirt-disk-drv-tap", False)

    def testBootParavirtDiskDrvTapQCow(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_TAP
        disk.driver_type = VirtualDisk.DRIVER_TAP_QCOW
        g.disks.append(disk)
        self._compare(g, "boot-paravirt-disk-drv-tap-qcow", False)

    def testBootParavirtManyDisks(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk("/tmp/test2.img")
        disk.driver_name = VirtualDisk.DRIVER_TAP
        disk.driver_type = VirtualDisk.DRIVER_TAP_QCOW

        g.disks.append(get_filedisk("/tmp/test1.img"))
        g.disks.append(disk)
        g.disks.append(get_blkdisk())
        self._compare(g, "boot-paravirt-many-disks", False)

    def testBootFullyvirtDiskFile(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk())
        self._compare(g, "boot-fullyvirt-disk-file", False)

    def testBootFullyvirtDiskBlock(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_blkdisk())
        self._compare(g, "boot-fullyvirt-disk-block", False)




    def testInstallParavirtDiskFile(self):
        g = get_basic_paravirt_guest()
        g.disks.append(get_filedisk())
        self._compare(g, "install-paravirt-disk-file", True)

    def testInstallParavirtDiskBlock(self):
        g = get_basic_paravirt_guest()
        g.disks.append(get_blkdisk())
        self._compare(g, "install-paravirt-disk-block", True)

    def testInstallParavirtDiskDrvPhy(self):
        g = get_basic_paravirt_guest()
        disk = get_blkdisk()
        disk.driver_name = VirtualDisk.DRIVER_PHY
        g.disks.append(disk)
        self._compare(g, "install-paravirt-disk-drv-phy", True)

    def testInstallParavirtDiskDrvFile(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_FILE
        g.disks.append(disk)
        self._compare(g, "install-paravirt-disk-drv-file", True)

    def testInstallParavirtDiskDrvTap(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_TAP
        g.disks.append(disk)
        self._compare(g, "install-paravirt-disk-drv-tap", True)

    def testInstallParavirtDiskDrvTapQCow(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_TAP
        disk.driver_type = VirtualDisk.DRIVER_TAP_QCOW
        g.disks.append(disk)
        self._compare(g, "install-paravirt-disk-drv-tap-qcow", True)

    def testInstallParavirtManyDisks(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk("/tmp/test2.img")
        disk.driver_name = VirtualDisk.DRIVER_TAP
        disk.driver_type = VirtualDisk.DRIVER_TAP_QCOW

        g.disks.append(get_filedisk("/tmp/test1.img"))
        g.disks.append(disk)
        g.disks.append(get_blkdisk())
        self._compare(g, "install-paravirt-many-disks", True)

    def testInstallFullyvirtDiskFile(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk())
        self._compare(g, "install-fullyvirt-disk-file", True)

    def testInstallFullyvirtDiskBlock(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_blkdisk())
        self._compare(g, "install-fullyvirt-disk-block", True)

    def testInstallFVPXE(self):
        g = get_basic_fullyvirt_guest()
        g.installer = virtinst.PXEInstaller(type="xen", os_type="hvm",
                                            conn=g.conn)
        g.disks.append(get_filedisk())
        self._compare(g, "install-fullyvirt-pxe", True)

    def testBootFVPXE(self):
        g = get_basic_fullyvirt_guest()
        g.installer = virtinst.PXEInstaller(type="xen", os_type="hvm",
                                            conn=g.conn)
        g.disks.append(get_filedisk())
        self._compare(g, "boot-fullyvirt-pxe", False)

    def testInstallFVPXENoDisks(self):
        g = get_basic_fullyvirt_guest()
        g.installer = virtinst.PXEInstaller(type="xen", os_type="hvm",
                                            conn=g.conn)
        self._compare(g, "install-fullyvirt-pxe-nodisks", True)

    def testBootFVPXENoDisks(self):
        g = get_basic_fullyvirt_guest()
        g.installer = virtinst.PXEInstaller(type="xen", os_type="hvm",
                                            conn=g.conn)
        self._compare(g, "boot-fullyvirt-pxe-nodisks", False)

    def testInstallFVLiveCD(self):
        g = get_basic_fullyvirt_guest()
        g.installer = virtinst.LiveCDInstaller(type="xen", os_type="hvm",
                                               conn=g.conn,
                                               location="/dev/loop0")
        self._compare(g, "install-fullyvirt-livecd", False)

    def testInstallFVImport(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk())
        g.installer = virtinst.ImportInstaller(type="xen", os_type="hvm",
                                               conn=g.conn)
        self._compare(g, "install-fullyvirt-import", False)

    def testInstallPVImport(self):
        g = get_basic_paravirt_guest()
        g.disks.append(get_filedisk())
        g.installer = virtinst.ImportInstaller(type="xen", os_type="xen",
                                               conn=g.conn)
        self._compare(g, "install-paravirt-import", False)

    def testQEMUDriverName(self):
        # Swap out _util.get_uri_driver for a fake method that always
        # returns a qemu driver, to trick VirtualDisk into giving us what we
        # want
        def new_get_uri(ignore):
            return "qemu:///system"

        oldgetdriver = VirtualDisk._get_uri
        try:
            VirtualDisk._get_uri = new_get_uri
            g = get_basic_fullyvirt_guest()
            g.disks.append(get_blkdisk())
            self._compare(g, "misc-qemu-driver-name", True)

            g = get_basic_fullyvirt_guest()
            g.disks.append(get_filedisk())
            self._compare(g, "misc-qemu-driver-type", True)
        finally:
            VirtualDisk._get_uri = oldgetdriver

    def testXMLEscaping(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk("/tmp/ISO&'&s"))
        self._compare(g, "misc-xml-escaping", True)


if __name__ == "__main__":
    unittest.main()

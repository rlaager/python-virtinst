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

import virtinst
from virtinst import VirtualDisk
from virtinst import VirtualAudio
from virtinst import VirtualNetworkInterface
from virtinst import VirtualHostDeviceUSB, VirtualHostDevicePCI
from virtinst import VirtualCharDevice
from virtinst import VirtualVideoDevice
import tests

conn = tests.open_testdriver()

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

def get_basic_fullyvirt_guest(typ="xen"):
    g = virtinst.FullVirtGuest(connection=conn, type=typ,
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

def get_floppy(path="/default-pool/testvol1.img"):
    return VirtualDisk(path, conn=conn, device=VirtualDisk.DEVICE_FLOPPY)

def get_filedisk(path="/tmp/test.img"):
    return VirtualDisk(path, size=.0001, conn=conn)

def get_blkdisk():
    return VirtualDisk("/dev/loop0", conn=conn)

def get_virtual_network():
    dev = virtinst.VirtualNetworkInterface()
    dev.macaddr = "11:22:33:44:55:66"
    dev.type = virtinst.VirtualNetworkInterface.TYPE_VIRTUAL
    dev.network = "default"
    return dev

class TestXMLConfig(unittest.TestCase):

    def _compare(self, xenguest, filebase, install):
        filename = os.path.join("tests/xmlconfig-xml", filebase + ".xml")
        xenguest._prepare_install(progress.BaseMeter())
        try:
            actualXML = xenguest.get_config_xml(install=install)
            tests.diff_compare(actualXML, filename)
            # Libvirt throws errors since we are defining domain
            # type='xen', when test driver can only handle type='test'
            # Sanitize the XML so we can define
            actualXML = actualXML.replace("<domain type='xen'>",
                                          "<domain type='test'>")
            actualXML = actualXML.replace(">linux<", ">xen<")

            # Should probably break this out into a separate function
            dom = xenguest.conn.defineXML(actualXML)
            dom.create()
            dom.destroy()
            dom.undefine()
        finally:
            xenguest._cleanup_install()


    def testBootParavirtDiskFile(self):
        g = get_basic_paravirt_guest()
        g.disks.append(get_filedisk())
        self._compare(g, "boot-paravirt-disk-file", False)

    def testBootParavirtDiskFileBlktapCapable(self):
        oldblktap = virtinst._util.is_blktap_capable
        try:
            virtinst._util.is_blktap_capable = lambda: True
            g = get_basic_paravirt_guest()
            g.disks.append(get_filedisk())
            self._compare(g, "boot-paravirt-disk-drv-tap", False)
        finally:
            virtinst._util.is_blktap_capable = oldblktap

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

    def testDoubleInstall(self):
        # Make sure that installing twice generates the same XML, to ensure
        # we aren't polluting the device list during the install process
        g = get_basic_fullyvirt_guest()
        g.installer = virtinst.LiveCDInstaller(type="xen", os_type="hvm",
                                               conn=g.conn,
                                               location="/dev/loop0")
        self._compare(g, "install-fullyvirt-livecd", False)
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

            VirtualDisk._get_uri = new_get_uri
            g = get_basic_fullyvirt_guest()
            g.disks.append(get_filedisk())
            self._compare(g, "misc-qemu-driver-type", True)

            VirtualDisk._get_uri = new_get_uri
            g = get_basic_fullyvirt_guest()
            g.disks.append(get_filedisk("/default-pool/iso-vol"))
            self._compare(g, "misc-qemu-iso-disk", True)
        finally:
            VirtualDisk._get_uri = oldgetdriver

    def testXMLEscaping(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk("/tmp/ISO&'&s"))
        self._compare(g, "misc-xml-escaping", True)

    # OS Type/Version configurations
    def testF10(self):
        g = get_basic_fullyvirt_guest("kvm")
        g.os_type = "linux"
        g.os_variant = "fedora10"
        g.installer = virtinst.PXEInstaller(type="kvm", os_type="hvm",
                                            conn=g.conn)
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        self._compare(g, "install-f10", True)

    def testF11(self):
        g = get_basic_fullyvirt_guest("kvm")
        g.os_type = "linux"
        g.os_variant = "fedora11"
        g.installer = virtinst.DistroInstaller(type="kvm", os_type="hvm",
                                               conn=g.conn,
                                               location="/default-pool/default-vol")
        g.installer.cdrom = True
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        self._compare(g, "install-f11", False)

    def testF11Xen(self):
        g = get_basic_fullyvirt_guest("xen")
        g.os_type = "linux"
        g.os_variant = "fedora11"
        g.installer = virtinst.DistroInstaller(type="xen", os_type="hvm",
                                               conn=g.conn,
                                               location="/default-pool/default-vol")
        g.installer.cdrom = True
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        self._compare(g, "install-f11-xen", False)

    def testBootWindows(self):
        g = get_basic_fullyvirt_guest("kvm")
        g.os_type = "windows"
        g.os_variant = "winxp"
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        self._compare(g, "boot-windowsxp-kvm", False)

    def testInstallWindowsKVM(self):
        g = get_basic_fullyvirt_guest("kvm")
        g.os_type = "windows"
        g.os_variant = "winxp"
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        self._compare(g, "install-windowsxp-kvm", True)

    def testInstallWindowsXenNew(self):
        orig_ver_func = libvirt.getVersion
        def old_xen_ver(drv=None):
            libver = orig_ver_func()
            if drv:
                return (libver, 3000001)
            return orig_ver_func(drv)

        def new_xen_ver(drv=None):
            libver = orig_ver_func()
            if drv:
                return (libver, 3100000)
            return orig_ver_func(drv)

        g = get_basic_fullyvirt_guest("xen")
        g.os_type = "windows"
        g.os_variant = "winxp"
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())

        try:
            for f, xml in [(old_xen_ver, "install-windowsxp-xenold"),
                           (new_xen_ver, "install-windowsxp-xennew")]:
                libvirt.getVersion = f
                self._compare(g, xml, True)
        finally:
            libvirt.getVersion = orig_ver_func


    # Device heavy configurations
    def testManyDisks2(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   device=VirtualDisk.DEVICE_CDROM))
        g.disks.append(VirtualDisk(conn=g.conn, path=None,
                                   device=VirtualDisk.DEVICE_CDROM,
                                   bus="scsi"))
        g.disks.append(VirtualDisk(conn=g.conn, path=None,
                                   device=VirtualDisk.DEVICE_FLOPPY))
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   device=VirtualDisk.DEVICE_FLOPPY))
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   bus="virtio"))

        g.installer = virtinst.PXEInstaller(type="xen", os_type="hvm",
                                            conn=g.conn)
        self._compare(g, "boot-many-disks2", False)

    def testManyNICs(self):
        g = get_basic_fullyvirt_guest()
        net1 = VirtualNetworkInterface(type="user",
                                       macaddr="11:11:11:11:11:11")
        net2 = get_virtual_network()
        net3 = get_virtual_network()
        net3.model = "e1000"
        net4 = VirtualNetworkInterface(bridge="foobr0",
                                       macaddr="22:22:22:22:22:22")

        g.nics.append(net1)
        g.nics.append(net2)
        g.nics.append(net3)
        g.nics.append(net4)
        g.installer = virtinst.PXEInstaller(type="xen", os_type="hvm",
                                            conn=g.conn)
        self._compare(g, "boot-many-nics", False)

    def testManyHostdevs(self):
        g = get_basic_fullyvirt_guest()
        dev1 = VirtualHostDeviceUSB(g.conn)
        dev1.product = "0x1234"
        dev1.vendor = "0x4321"

        dev2 = VirtualHostDevicePCI(g.conn)
        dev2.bus = "0x11"
        dev2.slot = "0x22"
        dev2.function = "0x33"

        g.hostdevs.append(dev1)
        g.hostdevs.append(dev2)
        g.installer = virtinst.PXEInstaller(type="xen", os_type="hvm",
                                            conn=g.conn)
        self._compare(g, "boot-many-hostdevs", False)

    def testManySounds(self):
        g = get_basic_fullyvirt_guest()
        g.sound_devs.append(VirtualAudio("sb16", conn=g.conn))
        g.sound_devs.append(VirtualAudio("es1370", conn=g.conn))
        g.sound_devs.append(VirtualAudio("pcspk", conn=g.conn))

        g.installer = virtinst.PXEInstaller(type="xen", os_type="hvm",
                                            conn=g.conn)
        self._compare(g, "boot-many-sounds", False)

    def testManyChars(self):
        g = get_basic_fullyvirt_guest()
        dev1 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_SERIAL,
                                                  VirtualCharDevice.CHAR_NULL)
        dev2 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_PARALLEL,
                                                  VirtualCharDevice.CHAR_UNIX)
        dev2.source_path = "/tmp/foobar"
        dev3 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_SERIAL,
                                                  VirtualCharDevice.CHAR_TCP)
        dev3.protocol = "telnet"
        dev3.source_host = "my.source.host"
        dev3.source_port = "1234"
        dev4 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_PARALLEL,
                                                  VirtualCharDevice.CHAR_UDP)
        dev4.bind_host = "my.bind.host"
        dev4.bind_port = "1111"
        dev4.source_host = "my.source.host"
        dev4.source_port = "2222"

        g.add_device(dev1)
        g.add_device(dev2)
        g.add_device(dev3)
        g.add_device(dev4)
        g.installer = virtinst.PXEInstaller(type="xen", os_type="hvm",
                                            conn=g.conn)
        self._compare(g, "boot-many-chars", False)

    def testManyDevices(self):
        g = get_basic_fullyvirt_guest()

        # Hostdevs
        dev1 = VirtualHostDeviceUSB(g.conn)
        dev1.product = "0x1234"
        dev1.vendor = "0x4321"
        g.hostdevs.append(dev1)

        # Sound devices
        g.sound_devs.append(VirtualAudio("sb16", conn=g.conn))
        g.sound_devs.append(VirtualAudio("es1370", conn=g.conn))

        # Disk devices
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   device=VirtualDisk.DEVICE_FLOPPY))
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   bus="scsi"))
        d3 = VirtualDisk(conn=g.conn, path="/default-pool/testvol1.img",
                         bus="scsi", driverName="qemu")
        g.disks.append(d3)

        # Network devices
        net1 = get_virtual_network()
        net1.model = "e1000"
        net2 = VirtualNetworkInterface(type="user",
                                       macaddr="11:11:11:11:11:11")
        g.nics.append(net1)
        g.nics.append(net2)

        # Character devices
        cdev1 = VirtualCharDevice.get_dev_instance(g.conn,
                                                   VirtualCharDevice.DEV_SERIAL,
                                                   VirtualCharDevice.CHAR_NULL)
        cdev2 = VirtualCharDevice.get_dev_instance(g.conn,
                                                   VirtualCharDevice.DEV_PARALLEL,
                                                   VirtualCharDevice.CHAR_UNIX)
        cdev2.source_path = "/tmp/foobar"
        g.add_device(cdev1)
        g.add_device(cdev2)

        # Video Devices
        vdev1 = VirtualVideoDevice(g.conn)
        vdev1.model_type = "vmvga"

        vdev2 = VirtualVideoDevice(g.conn)
        vdev2.model_type = "cirrus"
        vdev2.vram = 10 * 1024
        vdev2.heads = 3
        g.add_device(vdev1)
        g.add_device(vdev2)

        g.clock.offset = "localtime"

        seclabel = virtinst.Seclabel(g.conn)
        seclabel.type = seclabel.SECLABEL_TYPE_STATIC
        seclabel.model = "selinux"
        seclabel.label = "foolabel"
        seclabel.imagelabel = "imagelabel"
        g.seclabel = seclabel

        g.installer = virtinst.PXEInstaller(type="xen", os_type="hvm",
                                            conn=g.conn)
        self._compare(g, "boot-many-devices", False)

if __name__ == "__main__":
    unittest.main()

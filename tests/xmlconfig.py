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
from virtinst import VirtualController
from virtinst import VirtualWatchdog
from virtinst import VirtualInputDevice
import utils

conn = utils.open_testdriver()
scratch = os.path.join(os.getcwd(), "tests", "testscratchdir")

def get_basic_paravirt_guest(testconn=conn, installer=None):
    g = virtinst.ParaVirtGuest(connection=testconn, type="xen")
    g.name = "TestGuest"
    g.memory = int(200)
    g.maxmemory = int(400)
    g.uuid = "12345678-1234-1234-1234-123456789012"
    g.boot = ["/boot/vmlinuz", "/boot/initrd"]
    g.graphics = (True, "vnc", None, "ja")
    g.vcpus = 5

    if installer:
        g.installer = installer

    g.installer._scratchdir = scratch
    return g

def get_basic_fullyvirt_guest(typ="xen", testconn=conn, installer=None):
    g = virtinst.FullVirtGuest(connection=testconn, type=typ,
                               emulator="/usr/lib/xen/bin/qemu-dm",
                               arch="i686")
    g.name = "TestGuest"
    g.memory = int(200)
    g.maxmemory = int(400)
    g.uuid = "12345678-1234-1234-1234-123456789012"
    g.cdrom = "/dev/loop0"
    g.graphics = (True, "sdl")
    g.features['pae'] = 0
    g.vcpus = 5
    if installer:
        g.installer = installer

    g.installer._scratchdir = scratch
    return g

def make_import_installer(os_type="hvm"):
    inst = virtinst.ImportInstaller(type="xen", os_type=os_type, conn=conn)
    return inst

def make_distro_installer(location="/default-pool/default-vol", gtype="xen"):
    inst = virtinst.DistroInstaller(type=gtype, os_type="hvm", conn=conn,
                                    location=location)
    return inst

def make_live_installer(location="/dev/loop0", gtype="xen"):
    inst = virtinst.LiveCDInstaller(type=gtype, os_type="hvm",
                                    conn=conn, location=location)
    return inst

def make_pxe_installer(gtype="xen"):
    inst = virtinst.PXEInstaller(type=gtype, os_type="hvm", conn=conn)
    return inst

def build_win_kvm(path=None):
    g = get_basic_fullyvirt_guest("kvm")
    g.os_type = "windows"
    g.os_variant = "winxp"
    g.disks.append(get_filedisk(path))
    g.disks.append(get_blkdisk())
    g.nics.append(get_virtual_network())
    g.add_device(VirtualAudio())
    g.add_device(VirtualVideoDevice(g.conn))

    return g

def get_floppy(path=None):
    if not path:
        path = "/default-pool/testvol1.img"
    return VirtualDisk(path, conn=conn, device=VirtualDisk.DEVICE_FLOPPY)

def get_filedisk(path=None):
    if not path:
        path = "/tmp/test.img"
    return VirtualDisk(path, size=.0001, conn=conn)

def get_blkdisk(path="/dev/loop0"):
    return VirtualDisk(path, conn=conn)

def get_virtual_network():
    dev = virtinst.VirtualNetworkInterface()
    dev.macaddr = "11:22:33:44:55:66"
    dev.type = virtinst.VirtualNetworkInterface.TYPE_VIRTUAL
    dev.network = "default"
    return dev

def qemu_uri():
    return "qemu:///system"

def xen_uri():
    return "xen:///"

def build_xmlfile(filebase):
    if not filebase:
        return None
    return os.path.join("tests/xmlconfig-xml", filebase + ".xml")

class TestXMLConfig(unittest.TestCase):

    def tearDown(self):
        if os.path.exists(scratch):
            os.rmdir(scratch)

    def _compare(self, guest, filebase, do_install, do_disk_boot=False):
        filename = build_xmlfile(filebase)

        guest._prepare_install(progress.BaseMeter())
        try:
            actualXML = guest.get_config_xml(install=do_install,
                                             disk_boot=do_disk_boot)

            utils.diff_compare(actualXML, filename)
            utils.test_create(guest.conn, actualXML)
        finally:
            guest._cleanup_install()

    def _testInstall(self, guest,
                     instxml=None, bootxml=None, contxml=None):
        instname = build_xmlfile(instxml)
        bootname = build_xmlfile(bootxml)
        contname = build_xmlfile(contxml)
        consolecb = None
        meter = None
        removeOld = None
        wait = True
        dom = None

        old_getxml = guest.get_config_xml
        def new_getxml(install=True, disk_boot=False):
            xml = old_getxml(install, disk_boot)
            return utils.sanitize_xml_for_define(xml)
        guest.get_config_xml = new_getxml

        try:
            dom = guest.start_install(consolecb, meter, removeOld, wait)
            dom.destroy()

            # Replace kernel/initrd with known info
            if (guest.installer._install_bootconfig and
                guest.installer._install_bootconfig.kernel):
                guest.installer._install_bootconfig.kernel = "kernel"
                guest.installer._install_bootconfig.initrd = "initrd"

            xmlinst = guest.get_config_xml(True, False)
            xmlboot = guest.get_config_xml(False, False)
            xmlcont = guest.get_config_xml(True, True)

            if instname:
                utils.diff_compare(xmlinst, instname)
            if contname:
                utils.diff_compare(xmlcont, contname)
            if bootname:
                utils.diff_compare(xmlboot, bootname)

            if guest.get_continue_inst():
                guest.continue_install(consolecb, meter, wait)

        finally:
            if dom:
                try:
                    dom.destroy()
                except:
                    pass
                try:
                    dom.undefine()
                except:
                    pass


    def conn_function_wrappers(self, guest, funcargs,
                               func=None,
                               conn_version=None,
                               conn_uri=None,
                               libvirt_version=None):
        testconn = guest
        if isinstance(guest, virtinst.Guest):
            testconn = guest.conn

        def set_func(newfunc, funcname, obj, force=False):
            if newfunc or force:
                orig = None
                if hasattr(obj, funcname):
                    orig = getattr(obj, funcname)

                setattr(obj, funcname, newfunc)
                return orig, True

            return None, False

        def set_version(newfunc, force=False):
            return set_func(newfunc, "getVersion", testconn, force)
        def set_uri(newfunc, force=False):
            return set_func(newfunc, "getURI", testconn, force)
        def set_libvirt_version(newfunc, force=False):
            return set_func(newfunc, "getVersion", libvirt, force)

        old_version = None
        old_uri = None
        old_libvirt_version = None
        try:
            old_version = set_version(conn_version)
            old_uri = set_uri(conn_uri)
            old_libvirt_version = set_libvirt_version(libvirt_version)

            if not func:
                func = self._compare
            func(*funcargs)
        finally:
            set_version(*old_version)
            set_uri(*old_uri)
            set_libvirt_version(*old_libvirt_version)

    def testBootParavirtDiskFile(self):
        g = get_basic_paravirt_guest()
        g.disks.append(get_filedisk("/tmp/somerandomfilename.img"))
        self._compare(g, "boot-paravirt-disk-file", False)

        # Just cram some post_install_checks in here
        try:
            g.post_install_check()
            raise AssertionError("Expected OSError, none caught.")
        except OSError:
            pass

        g.disks[0].path = "virt-install"
        self.assertEquals(g.post_install_check(), False)

        g.disks[0].driver_type = "raw"
        self.assertEquals(g.post_install_check(), False)

        g.disks[0].driver_type = "foobar"
        self.assertEquals(g.post_install_check(), True)

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
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        g.disks.append(get_filedisk())
        self._compare(g, "install-fullyvirt-pxe", True)

    def testBootFVPXE(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        g.disks.append(get_filedisk())
        self._compare(g, "boot-fullyvirt-pxe", False)

    def testBootFVPXEAlways(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        g.disks.append(get_filedisk())

        g.installer.bootconfig.bootorder = [
            g.installer.bootconfig.BOOT_DEVICE_NETWORK]
        g.installer.bootconfig.enable_bootmenu = True
        g.seclabel.model = "default"

        self._compare(g, "boot-fullyvirt-pxe-always", False)

    def testInstallFVPXENoDisks(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        self._compare(g, "install-fullyvirt-pxe-nodisks", True)

    def testBootFVPXENoDisks(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        self._compare(g, "boot-fullyvirt-pxe-nodisks", False)

    def testInstallFVLiveCD(self):
        i = make_live_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        self._compare(g, "install-fullyvirt-livecd", False)

    def testDoubleInstall(self):
        # Make sure that installing twice generates the same XML, to ensure
        # we aren't polluting the device list during the install process
        i = make_live_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        self._compare(g, "install-fullyvirt-livecd", False)
        self._compare(g, "install-fullyvirt-livecd", False)

    def testDefaultDeviceRemoval(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk())

        inp = VirtualInputDevice(g.conn)
        cons = VirtualCharDevice.get_dev_instance(conn,
                                VirtualCharDevice.DEV_CONSOLE,
                                VirtualCharDevice.CHAR_PTY)
        g.add_device(inp)
        g.add_device(cons)

        g.remove_device(inp)
        g.remove_device(cons)

        self._compare(g, "boot-default-device-removal", False)

    def testOSDeviceDefaultChange(self):
        """
        Make sure device defaults are properly changed if we change OS
        distro/variant mid process
        """
        i = make_distro_installer(gtype="kvm")
        g = get_basic_fullyvirt_guest("kvm", installer=i)

        do_install = False
        g.installer.cdrom = True
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())

        # Call get_config_xml to set first round of defaults without an
        # os_variant set
        fargs = (do_install,)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri,
                                    func=g.get_config_xml)

        g.os_variant = "fedora11"
        fargs = (g, "install-f11", do_install)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testInstallFVImport(self):
        i = make_import_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.disks.append(get_filedisk())
        self._compare(g, "install-fullyvirt-import", False)

    def testInstallFVImportKernel(self):
        i = make_import_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.disks.append(get_filedisk())
        g.installer.bootconfig.kernel = "kernel"
        g.installer.bootconfig.initrd = "initrd"
        g.installer.bootconfig.kernel_args = "my kernel args"

        self._compare(g, "install-fullyvirt-import-kernel", False)

    def testInstallFVImportMulti(self):
        i = make_import_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.installer.bootconfig.enable_bootmenu = False
        g.installer.bootconfig.bootorder = ["hd", "fd", "cdrom", "network"]
        g.disks.append(get_filedisk())
        self._compare(g, "install-fullyvirt-import-multiboot", False)

    def testInstallPVImport(self):
        i = make_import_installer("xen")
        g = get_basic_paravirt_guest(installer=i)

        g.disks.append(get_filedisk())
        self._compare(g, "install-paravirt-import", False)

    def testQEMUDriverName(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_blkdisk())
        fargs = (g, "misc-qemu-driver-name", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk("/iscsi-pool/diskvol1"))
        fargs = (g, "misc-qemu-driver-type", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk("/default-pool/iso-vol"))
        fargs = (g, "misc-qemu-iso-disk", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk("/default-pool/iso-vol"))
        g.disks[0].driver_type = "qcow2"
        fargs = (g, "misc-qemu-driver-overwrite", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testXMLEscaping(self):
        g = get_basic_fullyvirt_guest()
        g.description = "foooo barrrr \n baz && snarf. '' \"\" @@$\n"
        g.disks.append(get_filedisk("/tmp/ISO&'&s"))
        self._compare(g, "misc-xml-escaping", True)

    # OS Type/Version configurations
    def testF10(self):
        i = make_pxe_installer(gtype="kvm")
        g = get_basic_fullyvirt_guest("kvm", installer=i)

        g.os_type = "linux"
        g.os_variant = "fedora10"
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        fargs = (g, "install-f10", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testF11(self):
        i = make_distro_installer(gtype="kvm")
        g = get_basic_fullyvirt_guest("kvm", installer=i)

        g.os_type = "linux"
        g.os_variant = "fedora11"
        g.installer.cdrom = True
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        fargs = (g, "install-f11", False)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testF11AC97(self):
        def build_guest():
            i = make_distro_installer(gtype="kvm")
            g = get_basic_fullyvirt_guest("kvm", installer=i)

            g.os_type = "linux"
            g.os_variant = "fedora11"
            g.installer.cdrom = True
            g.disks.append(get_floppy())
            g.disks.append(get_filedisk())
            g.disks.append(get_blkdisk())
            g.nics.append(get_virtual_network())
            g.add_device(VirtualAudio())
            return g

        def libvirt_nosupport_ac97(drv=None):
            libver = 5000
            if drv:
                return (libver, libver)
            return libver

        def conn_nosupport_ac97():
            return 10000

        def conn_support_ac97():
            return 11000

        g = build_guest()
        fargs = (g, "install-f11-ac97", False)
        self.conn_function_wrappers(g, fargs,
                                    conn_uri=qemu_uri,
                                    conn_version=conn_support_ac97)

        g = build_guest()
        fargs = (g, "install-f11-noac97", False)
        self.conn_function_wrappers(g, fargs,
                                    libvirt_version=libvirt_nosupport_ac97,
                                    conn_uri=qemu_uri)

        g = build_guest()
        fargs = (g, "install-f11-noac97", False)
        self.conn_function_wrappers(g, fargs,
                                    conn_version=conn_nosupport_ac97,
                                    conn_uri=qemu_uri)

    def testKVMKeymap(self):
        def conn_nosupport_autokeymap():
            return 10000
        def conn_support_autokeymap():
            return 11000

        def test1():
            g = virtinst.VirtualGraphics(conn=conn, type="vnc")
            self.assertTrue(g.keymap != None)
        self.conn_function_wrappers(conn, (), func=test1,
                                    conn_uri=qemu_uri,
                                    conn_version=conn_nosupport_autokeymap)

        def test2():
            g = virtinst.VirtualGraphics(conn=conn, type="vnc")
            self.assertTrue(g.keymap == None)
        self.conn_function_wrappers(conn, (), func=test2,
                                    conn_uri=qemu_uri,
                                    conn_version=conn_support_autokeymap)


    def testF11Qemu(self):
        i = make_distro_installer(gtype="qemu")
        g = get_basic_fullyvirt_guest("qemu", installer=i)

        g.os_type = "linux"
        g.os_variant = "fedora11"
        g.installer.cdrom = True
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        fargs = (g, "install-f11-qemu", False)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testF11Xen(self):
        i = make_distro_installer(gtype="xen")
        g = get_basic_fullyvirt_guest("xen", installer=i)

        g.os_type = "linux"
        g.os_variant = "fedora11"
        g.installer.cdrom = True
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        fargs = (g, "install-f11-xen", False)
        self.conn_function_wrappers(g, fargs, conn_uri=xen_uri)

    def testInstallWindowsKVM(self):
        g = build_win_kvm("/default-pool/winxp.img")
        fargs = (g, "winxp-kvm-stage1", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testContinueWindowsKVM(self):
        g = build_win_kvm("/default-pool/winxp.img")
        fargs = (g, "winxp-kvm-stage2", True, True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testBootWindowsKVM(self):
        g = build_win_kvm("/default-pool/winxp.img")
        fargs = (g, "winxp-kvm-stage3", False)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)


    def testInstallWindowsXenNew(self):
        def old_xen_ver():
            return 3000001

        def new_xen_ver():
            return 3100000


        g = get_basic_fullyvirt_guest("xen")
        g.os_type = "windows"
        g.os_variant = "winxp"
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        g.add_device(VirtualAudio())

        for f, xml in [(old_xen_ver, "install-windowsxp-xenold"),
                       (new_xen_ver, "install-windowsxp-xennew")]:

            fargs = (g, xml, True)
            self.conn_function_wrappers(g, fargs,
                                        conn_version=f, conn_uri=xen_uri)


    # Device heavy configurations
    def testManyDisks2(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   device=VirtualDisk.DEVICE_CDROM,
                                   driverType="raw"))
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   device=VirtualDisk.DEVICE_DISK,
                                   driverName="qemu", format="qcow2"))
        g.disks.append(VirtualDisk(conn=g.conn, path=None,
                                   device=VirtualDisk.DEVICE_CDROM,
                                   bus="scsi"))
        g.disks.append(VirtualDisk(conn=g.conn, path=None,
                                   device=VirtualDisk.DEVICE_FLOPPY))
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   device=VirtualDisk.DEVICE_FLOPPY,
                                   driverName="phy", driverCache="none"))
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   bus="virtio", driverName="qemu",
                                   driverType="qcow2", driverCache="none"))

        self._compare(g, "boot-many-disks2", False)

    def testManyNICs(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        net1 = VirtualNetworkInterface(type="user",
                                       macaddr="11:11:11:11:11:11")
        net2 = get_virtual_network()
        net3 = get_virtual_network()
        net3.model = "e1000"
        net4 = VirtualNetworkInterface(bridge="foobr0",
                                       macaddr="22:22:22:22:22:22")
        net4.target_dev = "foo1"
        net5 = VirtualNetworkInterface(type="ethernet",
                                       macaddr="00:11:00:22:00:33")
        net5.source_dev = "testeth1"

        g.nics.append(net1)
        g.nics.append(net2)
        g.nics.append(net3)
        g.nics.append(net4)
        g.nics.append(net5)
        self._compare(g, "boot-many-nics", False)

    def testManyHostdevs(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        dev1 = VirtualHostDeviceUSB(g.conn)
        dev1.product = "0x1234"
        dev1.vendor = "0x4321"

        dev2 = VirtualHostDevicePCI(g.conn)
        dev2.bus = "0x11"
        dev2.slot = "0x22"
        dev2.function = "0x33"

        g.hostdevs.append(dev1)
        g.hostdevs.append(dev2)
        self._compare(g, "boot-many-hostdevs", False)

    def testManySounds(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.sound_devs.append(VirtualAudio("sb16", conn=g.conn))
        g.sound_devs.append(VirtualAudio("es1370", conn=g.conn))
        g.sound_devs.append(VirtualAudio("pcspk", conn=g.conn))
        g.sound_devs.append(VirtualAudio(conn=g.conn))

        self._compare(g, "boot-many-sounds", False)

    def testManyChars(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

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

        dev5 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_CHANNEL,
                                                  VirtualCharDevice.CHAR_PTY)
        dev5.target_type = dev5.CHAR_CHANNEL_TARGET_VIRTIO
        dev5.target_name = "foo.bar.frob"

        dev6 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_CONSOLE,
                                                  VirtualCharDevice.CHAR_PTY)
        dev6.target_type = dev5.CHAR_CONSOLE_TARGET_VIRTIO

        dev7 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_CONSOLE,
                                                  VirtualCharDevice.CHAR_PTY)

        dev8 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_CHANNEL,
                                                  VirtualCharDevice.CHAR_PTY)
        dev8.target_type = dev5.CHAR_CHANNEL_TARGET_GUESTFWD
        dev8.target_address = "1.2.3.4"
        dev8.target_port = "4567"

        g.add_device(dev1)
        g.add_device(dev2)
        g.add_device(dev3)
        g.add_device(dev4)
        g.add_device(dev5)
        g.add_device(dev6)
        g.add_device(dev7)
        g.add_device(dev8)
        self._compare(g, "boot-many-chars", False)

    def testManyDevices(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.description = "foooo barrrr somedesc"

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
        g.disks.append(VirtualDisk(conn=g.conn, path="/tmp", device="floppy"))
        d3 = VirtualDisk(conn=g.conn, path="/default-pool/testvol1.img",
                         bus="scsi", driverName="qemu")
        g.disks.append(d3)

        # Controller devices
        c1 = VirtualController.get_class_for_type(VirtualController.CONTROLLER_TYPE_IDE)(g.conn)
        c1.index = "3"
        c2 = VirtualController.get_class_for_type(VirtualController.CONTROLLER_TYPE_VIRTIOSERIAL)(g.conn)
        c2.ports = "32"
        c2.vectors = "17"
        g.add_device(c1)
        g.add_device(c2)

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

        vdev3 = VirtualVideoDevice(g.conn)
        vdev4 = VirtualVideoDevice(g.conn)
        vdev4.model_type = "qxl"

        g.add_device(vdev1)
        g.add_device(vdev2)
        g.add_device(vdev3)
        g.add_device(vdev4)

        wdev2 = VirtualWatchdog(g.conn)
        wdev2.model = "ib700"
        wdev2.action = "none"
        g.add_device(wdev2)

        # Check keymap autoconfig
        gdev1 = virtinst.VirtualGraphics(conn=g.conn, type="vnc")
        self.assertTrue(gdev1.keymap != None)
        gdev1.keymap = "en-us"

        # Check keymap None
        gdev2 = virtinst.VirtualGraphics(conn=g.conn, type="vnc")
        gdev2.keymap = None

        gdev3 = virtinst.VirtualGraphics(conn=g.conn, type="sdl")
        gdev4 = virtinst.VirtualGraphics(conn=g.conn, type="spice")

        gdev5 = virtinst.VirtualGraphics(conn=g.conn, type="sdl")
        gdev5.xauth = "fooxauth"
        gdev5.display = "foodisplay"
        g.add_device(gdev1)
        g.add_device(gdev2)
        g.add_device(gdev3)
        g.add_device(gdev4)
        g.add_device(gdev5)

        g.clock.offset = "localtime"

        g.seclabel.type = g.seclabel.SECLABEL_TYPE_STATIC
        g.seclabel.model = "selinux"
        g.seclabel.label = "foolabel"
        g.seclabel.imagelabel = "imagelabel"

        self._compare(g, "boot-many-devices", False)

    def testCpuset(self):
        testconn = libvirt.open("test:///default")
        g = get_basic_fullyvirt_guest(testconn=testconn)

        # Cpuset
        cpustr = g.generate_cpuset(g.conn, g.memory)
        g.cpuset = cpustr
        g.maxvcpus = 7

        g.cpu.model = "footest"
        g.cpu.vendor = "Intel"
        g.cpu.match = "minimum"

        g.cpu.threads = "2"
        g.cpu.sockets = "4"
        g.cpu.cores = "5"

        g.cpu.add_feature("x2apic", "force")
        g.cpu.add_feature("lahf_lm", "forbid")

        self._compare(g, "boot-cpuset", False)

        # Test CPU topology determining
        cpu = virtinst.CPU(g.conn)
        cpu.sockets = "2"
        cpu.set_topology_defaults(6)
        self.assertEquals([cpu.sockets, cpu.cores, cpu.threads], [2, 3, 1])

        cpu = virtinst.CPU(g.conn)
        cpu.cores = "4"
        cpu.set_topology_defaults(9)
        self.assertEquals([cpu.sockets, cpu.cores, cpu.threads], [2, 4, 1])

        cpu = virtinst.CPU(g.conn)
        cpu.threads = "3"
        cpu.set_topology_defaults(14)
        self.assertEquals([cpu.sockets, cpu.cores, cpu.threads], [4, 1, 3])

        cpu = virtinst.CPU(g.conn)
        cpu.sockets = 5
        cpu.cores = 2
        self.assertEquals(cpu.vcpus_from_topology(), 10)

        cpu = virtinst.CPU(g.conn)
        self.assertEquals(cpu.vcpus_from_topology(), 1)


    #
    # Full Install tests: try to mimic virt-install as much as possible
    #

    def testFullKVMRHEL6(self):
        i = make_distro_installer(location="tests/cli-test-xml/fakerhel6tree",
                                  gtype="kvm")
        g = get_basic_fullyvirt_guest("kvm", installer=i)
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk("/default-pool/rhel6.img"))
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        g.add_device(VirtualAudio())
        g.add_device(VirtualVideoDevice(g.conn))
        g.os_autodetect = True

        fargs = (g, "rhel6-kvm-stage1", "rhel6-kvm-stage2")
        self.conn_function_wrappers(g, fargs, func=self._testInstall,
                                    conn_uri=qemu_uri)

    def testFullKVMWinxp(self):
        g = build_win_kvm("/default-pool/winxp.img")
        fargs = (g, "winxp-kvm-stage1", "winxp-kvm-stage3", "winxp-kvm-stage2")
        self.conn_function_wrappers(g, fargs, func=self._testInstall,
                                    conn_uri=qemu_uri)

if __name__ == "__main__":
    unittest.main()

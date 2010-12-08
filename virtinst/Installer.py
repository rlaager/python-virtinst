#
# Common code for all guests
#
# Copyright 2006-2009  Red Hat, Inc.
# Jeremy Katz <katzj@redhat.com>
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

import os, errno
import struct
import platform
import logging
import copy

import _util
import virtinst
import XMLBuilderDomain
from XMLBuilderDomain import _xml_property
from virtinst import CapabilitiesParser
from virtinst import _virtinst as _
from VirtualDisk import VirtualDisk
from Boot import Boot

XEN_SCRATCH = "/var/lib/xen"
LIBVIRT_SCRATCH = "/var/lib/libvirt/boot"

def _get_scratchdir(typ):
    scratch = None
    if platform.system() == 'SunOS':
        scratch = '/var/tmp'

    if os.geteuid() == 0:
        if typ == "xen" and os.path.exists(XEN_SCRATCH):
            scratch = XEN_SCRATCH
        elif os.path.exists(LIBVIRT_SCRATCH):
            scratch = LIBVIRT_SCRATCH

    if not scratch:
        scratch = os.path.expanduser("~/.virtinst/boot")
        if not os.path.exists(scratch):
            os.makedirs(scratch, 0751)
        _util.selinux_restorecon(scratch)

    return scratch

class Installer(XMLBuilderDomain.XMLBuilderDomain):
    """
    Installer classes attempt to encapsulate all the parameters needed
    to 'install' a guest: essentially, booting the guest with the correct
    media for the OS install phase (if there is one), and setting up the
    guest to boot to the correct media for all subsequent runs.

    Some of the actual functionality:

        - Determining what type of install media has been requested, and
          representing it correctly to the Guest

        - Fetching install kernel/initrd or boot.iso from a URL

        - Setting the boot device as appropriate depending on whether we
          are booting into an OS install, or booting post-install

    Some of the information that the Installer needs to know to accomplish
    this:

        - Install media location (could be a URL, local path, ...)
        - Virtualization type (parameter 'os_type') ('xen', 'hvm', etc.)
        - Hypervisor name (parameter 'type') ('qemu', 'kvm', 'xen', etc.)
        - Guest architecture ('i686', 'x86_64')
    """

    _dumpxml_xpath = "/domain/os"
    def __init__(self, type="xen", location=None, boot=None,
                 extraargs=None, os_type=None, conn=None,
                 parsexml=None, parsexmlnode=None, caps=None):
        XMLBuilderDomain.XMLBuilderDomain.__init__(self, conn, parsexml,
                                                   parsexmlnode, caps=caps)

        self._type = None
        self._location = None
        self._initrd_injections = []
        self._cdrom = False
        self._os_type = None
        self._scratchdir = None
        self._arch = None
        self._machine = None
        self._loader = None
        self._install_bootconfig = Boot(self.conn)
        self._bootconfig = Boot(self.conn, parsexml, parsexmlnode)

        # Devices created/added during the prepare() stage
        self.install_devices = []

        if self._is_parse():
            return

        # FIXME: Better solution? Skip validating this since we may not be
        # able to install a VM of the host arch
        if self._get_caps():
            self._arch = self._get_caps().host.arch

        if type is None:
            type = "xen"
        self.type = type

        if not os_type is None:
            self.os_type = os_type
        else:
            self.os_type = "xen"
        if not location is None:
            self.location = location

        if not boot is None:
            self.boot = boot
        self.extraargs = extraargs

        self._tmpfiles = []

    def get_conn(self):
        return self._conn
    conn = property(get_conn)

    def _get_bootconfig(self):
        return self._bootconfig
    bootconfig = property(_get_bootconfig)

    # Hypervisor name (qemu, kvm, xen, lxc, etc.)
    def get_type(self):
        return self._type
    def set_type(self, val):
        self._type = val
    type = _xml_property(get_type, set_type,
                         xpath="./@type")

    # Virtualization type ('xen' == xen paravirt, or 'hvm)
    def get_os_type(self):
        return self._os_type
    def set_os_type(self, val):
        # Older libvirt back compat: if user specifies 'linux', convert
        # internally to newer equivalent value 'xen'
        if val == "linux":
            val = "xen"

        # XXX: Need to validate this: have some whitelist based on caps?
        self._os_type = val
    os_type = _xml_property(get_os_type, set_os_type,
                            xpath="./os/type")

    def get_arch(self):
        return self._arch
    def set_arch(self, val):
        # XXX: Sanitize to a consisten value (i368 -> i686)
        # XXX: Validate against caps
        self._arch = val
    arch = _xml_property(get_arch, set_arch,
                         xpath="./os/type/@arch")

    def _get_machine(self):
        return self._machine
    def _set_machine(self, val):
        self._machine = val
    machine = _xml_property(_get_machine, _set_machine,
                            xpath="./os/type/@machine")

    def _get_loader(self):
        return self._loader
    def _set_loader(self, val):
        self._loader = val
    loader = _xml_property(_get_loader, _set_loader,
                           xpath="./os/loader")

    def get_scratchdir(self):
        if not self.scratchdir_required():
            return None

        if not self._scratchdir:
            self._scratchdir = _get_scratchdir(self.type)
        return self._scratchdir
    scratchdir = property(get_scratchdir)

    def get_cdrom(self):
        return self._cdrom
    def set_cdrom(self, enable):
        if enable not in [True, False]:
            raise ValueError, _("Guest.cdrom must be a boolean type")
        self._cdrom = enable
    cdrom = property(get_cdrom, set_cdrom)

    def get_location(self):
        return self._location
    def set_location(self, val):
        self._location = val
    location = property(get_location, set_location)

    def get_initrd_injections(self):
        return self._initrd_injections
    def set_initrd_injections(self, val):
        self._initrd_injections = val
    initrd_injections = property(get_initrd_injections, set_initrd_injections)

    # kernel + initrd pair to use for installing as opposed to using a location
    def get_boot(self):
        return {"kernel" : self._install_bootconfig.kernel,
                "initrd" : self._install_bootconfig.initrd}
    def set_boot(self, val):
        self.cdrom = False
        boot = {}
        if type(val) == tuple:
            if len(val) != 2:
                raise ValueError, _("Must pass both a kernel and initrd")
            (k, i) = val
            boot = {"kernel": k, "initrd": i}

        elif type(val) == dict:
            if not val.has_key("kernel") or not val.has_key("initrd"):
                raise ValueError, _("Must pass both a kernel and initrd")
            boot = val

        elif type(val) == list:
            if len(val) != 2:
                raise ValueError, _("Must pass both a kernel and initrd")
            boot = {"kernel": val[0], "initrd": val[1]}

        else:
            raise ValueError, _("Kernel and initrd must be specified by "
                                "a list, dict, or tuple.")

        self._install_bootconfig.kernel = boot.get("kernel")
        self._install_bootconfig.initrd = boot.get("initrd")

    boot = property(get_boot, set_boot)

    # extra arguments to pass to the guest installer
    def get_extra_args(self):
        return self._install_bootconfig.kernel_args
    def set_extra_args(self, val):
        self._install_bootconfig.kernel_args = val
    extraargs = property(get_extra_args, set_extra_args)


    # Public helper methods
    def scratchdir_required(self):
        """
        Returns true if scratchdir is needed for the passed install parameters.
        Apps can use this to determine if they should attempt to ensure
        scratchdir permissions are adequate
        """
        return False

    # Private methods
    def _get_bootdev(self, isinstall, guest):
        raise NotImplementedError

    def _get_osblob_helper(self, guest, isinstall, bootconfig):
        ishvm = self.os_type == "hvm"
        conn = guest.conn
        arch = self.arch
        loader = self.loader
        if not loader and ishvm and self.type == "xen":
            loader = "/usr/lib/xen/boot/hvmloader"

        if not isinstall and not ishvm and not self.bootconfig.kernel:
            return "<bootloader>%s</bootloader>" % _util.pygrub_path(conn)

        osblob = "<os>\n"

        os_type = self.os_type
        # Hack for older libvirt: use old value 'linux' for best back compat,
        # new libvirt will adjust the value accordingly.
        if os_type == "xen" and self.type == "xen":
            os_type = "linux"

        osblob += "    <type"
        if arch:
            osblob += " arch='%s'" % arch
        if self.machine:
            osblob += " machine='%s'" % self.machine
        osblob += ">%s</type>\n" % os_type

        if loader:
            osblob += "    <loader>%s</loader>\n" % loader

        osblob += bootconfig.get_xml_config()
        osblob = _util.xml_append(osblob, "  </os>")

        return osblob


    # Method definitions

    def _get_xml_config(self, guest, isinstall):
        """
        Generate the portion of the guest xml that determines boot devices
        and parameters. (typically the <os></os> block)

        @param guest: Guest instance we are installing
        @type guest: L{Guest}
        @param isinstall: Whether we want xml for the 'install' phase or the
                          'post-install' phase.
        @type isinstall: C{bool}
        """
        bootdev = self._get_bootdev(isinstall, guest)
        if isinstall:
            bootconfig = self._install_bootconfig
        else:
            bootconfig = self.bootconfig

        if isinstall and not bootdev:
            # No install phase
            return

        bootconfig = copy.copy(bootconfig)
        if not bootconfig.bootorder:
            bootconfig.bootorder = [bootdev]

        return self._get_osblob_helper(guest, isinstall, bootconfig)

    def cleanup(self):
        """
        Remove any temporary files retrieved during installation
        """
        for f in self._tmpfiles:
            logging.debug("Removing " + f)
            os.unlink(f)
        self._tmpfiles = []
        self.install_devices = []

    def prepare(self, guest, meter):
        """
        Fetch any files needed for installation.
        @param guest: guest instance being installed
        @type L{Guest}
        @param meter: progress meter
        @type Urlgrabber ProgressMeter
        """
        raise NotImplementedError("Must be implemented in subclass")

    def post_install_check(self, guest):
        """
        Attempt to verify that installing to disk was successful.
        @param guest: guest instance that was installed
        @type L{Guest}
        """

        if _util.is_uri_remote(guest.conn.getURI()):
            # XXX: Use block peek for this?
            return True

        if (len(guest.disks) == 0 or
            guest.disks[0].device != VirtualDisk.DEVICE_DISK):
            return True

        disk = guest.disks[0]

        if _util.is_vdisk(disk.path):
            return True

        if (disk.driver_type and
            disk.driver_type not in [disk.DRIVER_TAP_RAW,
                                     disk.DRIVER_QEMU_RAW]):
            # Might be a non-raw format
            return True

        # Check for the 0xaa55 signature at the end of the MBR
        try:
            fd = os.open(disk.path, os.O_RDONLY)
        except OSError, (err, msg):
            logging.debug("Failed to open guest disk: %s" % msg)
            if err == errno.EACCES and os.geteuid() != 0:
                return True # non root might not have access to block devices
            else:
                raise

        buf = os.read(fd, 512)
        os.close(fd)
        return (len(buf) == 512 and
                struct.unpack("H", buf[0x1fe: 0x200]) == (0xaa55,))

    def detect_distro(self):
        """
        Attempt to detect the distro for the Installer's 'location'. If
        an error is encountered in the detection process (or if detection
        is not relevant for the Installer type), (None, None) is returned

        @returns: (distro type, distro variant) tuple
        """
        return (None, None)

    def guest_from_installer(self):
        """
        Return a L{Guest} instance wrapping the current installer.

        If all the appropriate values are present in the installer
        (conn, type, os_type, arch, machine), we have everything we need
        to determine what L{Guest} class is expected and what default values
        to pass it. This is a convenience method to save the API user from
        having to enter all these known details twice.
        """

        if not self.conn:
            raise ValueError(_("A connection must be specified."))

        guest, domain = CapabilitiesParser.guest_lookup(conn=self.conn,
                                                        caps=self._get_caps(),
                                                        os_type=self.os_type,
                                                        type=self.type,
                                                        arch=self.arch,
                                                        machine=self.machine)

        if self.os_type not in ["xen", "hvm"]:
            raise ValueError(_("No 'Guest' class for virtualization type '%s'"
                             % self.type))

        gobj = virtinst.Guest(installer=self, connection=self.conn)
        gobj.arch = guest.arch
        gobj.emulator = domain.emulator
        self.loader = domain.loader

        return gobj

# Back compat
Installer.get_install_xml = Installer.get_xml_config

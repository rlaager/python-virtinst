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

import _util
import virtinst
from virtinst import _virtinst as _
from VirtualDisk import VirtualDisk

XEN_SCRATCH="/var/lib/xen"
LIBVIRT_SCRATCH="/var/lib/libvirt/boot"

class Installer(object):
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
    def __init__(self, type = "xen", location = None, boot = None,
                 extraargs = None, os_type = None, conn = None):
        self._type = None
        self._location = None
        self._extraargs = None
        self._boot = None
        self._cdrom = False
        # XXX: We should set this default based on capabilities?
        self._os_type = "xen"
        self._conn = conn
        self._install_disk = None   # VirtualDisk that contains install media

        if type is None:
            type = "xen"
        self.type = type

        if not os_type is None:
            self.os_type = os_type
        if not location is None:
            self.location = location
        if not boot is None:
            self.boot = boot
        if not extraargs is None:
            self.extraargs = extraargs

        self._tmpfiles = []

    def get_install_disk(self):
        return self._install_disk
    install_disk = property(get_install_disk)

    def get_conn(self):
        return self._conn
    conn = property(get_conn)

    def get_type(self):
        return self._type
    def set_type(self, val):
        self._type = val
    type = property(get_type, set_type)

    def get_os_type(self):
        return self._os_type
    def set_os_type(self, val):
        # Older libvirt back compat: if user specifies 'linux', convert
        # internally to newer equivalent value 'xen'
        if val == "linux":
            val = "xen"

        # XXX: Need to validate this: have some whitelist based on caps?
        self._os_type = val
    os_type = property(get_os_type, set_os_type)

    def get_scratchdir(self):
        if platform.system() == 'SunOS':
            return '/var/tmp'
        if self.type == "xen" and os.path.exists(XEN_SCRATCH):
            return XEN_SCRATCH
        if os.geteuid() == 0 and os.path.exists(LIBVIRT_SCRATCH):
            return LIBVIRT_SCRATCH
        else:
            return os.path.expanduser("~/.virtinst/boot")
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

    # kernel + initrd pair to use for installing as opposed to using a location
    def get_boot(self):
        return self._boot
    def set_boot(self, val):
        self.cdrom = False
        if type(val) == tuple:
            if len(val) != 2:
                raise ValueError, _("Must pass both a kernel and initrd")
            (k, i) = val
            self._boot = {"kernel": k, "initrd": i}
        elif type(val) == dict:
            if not val.has_key("kernel") or not val.has_key("initrd"):
                raise ValueError, _("Must pass both a kernel and initrd")
            self._boot = val
        elif type(val) == list:
            if len(val) != 2:
                raise ValueError, _("Must pass both a kernel and initrd")
            self._boot = {"kernel": val[0], "initrd": val[1]}
        else:
            raise ValueError, _("Kernel and initrd must be specified by a list, dict, or tuple.")
    boot = property(get_boot, set_boot)

    # extra arguments to pass to the guest installer
    def get_extra_args(self):
        return self._extraargs
    def set_extra_args(self, val):
        self._extraargs = val
    extraargs = property(get_extra_args, set_extra_args)

    # Private methods

    def _get_osblob_helper(self, guest, isinstall, arch=None,
                           kernel=None, bootdev=None):

        # TODO: kernel should go away: we should be able to pull this
        #       directly from the installer. This may mean deprecating
        #       extraargs or something
        # TODO: arch should go away, this should be a property of the
        #       installer, not the guest.

        def get_param(obj, paramname):
            if hasattr(obj, paramname):
                return getattr(obj, paramname)
            return None

        ishvm = False
        if isinstance(guest, virtinst.FullVirtGuest):
            ishvm = True

        conn = guest.conn
        if not arch:
            arch = get_param(guest, "arch")
        loader = get_param(guest, "loader")

        osblob = ""
        if not isinstall and not ishvm:
            return "<bootloader>%s</bootloader>" % _util.pygrub_path(conn)

        osblob = "<os>\n"

        os_type = self.os_type
        # Hack for older libvirt: use old value 'linux' for best back compat,
        # new libvirt will adjust the value accordingly.
        if os_type == "xen" and self.type == "xen":
            os_type = "linux"

        if arch:
            osblob += "    <type arch='%s'>%s</type>\n" % (arch, os_type)
        else:
            osblob += "    <type>%s</type>\n" % os_type

        if loader:
            osblob += "    <loader>%s</loader>\n" % loader

        if isinstall and kernel and kernel["kernel"]:
            osblob += "    <kernel>%s</kernel>\n"   % _util.xml_escape(kernel["kernel"])
            osblob += "    <initrd>%s</initrd>\n"   % _util.xml_escape(kernel["initrd"])
            osblob += "    <cmdline>%s</cmdline>\n" % _util.xml_escape(kernel["extraargs"])
        elif bootdev is not None:
            osblob += "    <boot dev='%s'/>\n" % bootdev

        osblob += "  </os>"

        return osblob


    # Method definitions

    def cleanup(self):
        """
        Remove any temporary files retrieved during installation
        """
        for f in self._tmpfiles:
            logging.debug("Removing " + f)
            os.unlink(f)
        self._tmpfiles = []

    def prepare(self, guest, meter, distro=None):
        """
        Fetch any files needed for installation.
        @param guest: guest instance being installed
        @type L{Guest}
        @param meter: progress meter
        @type Urlgrabber ProgressMeter
        @param distro: Name of distro being installed
        @type C{str} name from Guest os dictionary
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

        if len(guest.disks) == 0 \
           or guest.disks[0].device != VirtualDisk.DEVICE_DISK:
            return True

        if _util.is_vdisk(guest.disks[0].path):
            return True

        # Check for the 0xaa55 signature at the end of the MBR
        try:
            fd = os.open(guest.disks[0].path, os.O_RDONLY)
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

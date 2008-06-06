# Installer for images
#
# Copyright 2007  Red Hat, Inc.
# David Lutterkort <dlutter@redhat.com>
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

import Guest
import ImageParser
import CapabilitiesParser as Cap
import os
import util

class ImageInstallerException(RuntimeError):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class ImageInstaller(Guest.Installer):
    """Installer for image-based guests"""
    def __init__(self, image, capabilities, boot_index = None):
        Guest.Installer.__init__(self)
        self._capabilities = capabilities
        self._image = image
        if boot_index is None:
            self._boot_caps = match_boots(self._capabilities,
                                     self.image.domain.boots)
            if self._boot_caps is None:
                raise ImageInstallerException(_("Could not find suitable boot descriptor for this host"))
        else:
            self._boot_caps = image.domain.boots[boot_index]

        self._guest = self._capabilities.guestForOSType(self._boot_caps.type, self._boot_caps.arch)
        if self._guest is None:
            raise PlatformMatchException(_("Unsupported virtualization type"))

        self._domain = self._guest.bestDomainType()
        self.type = self._domain.hypervisor_type
        self.arch = self._guest.arch

    def is_hvm(self):
        if self._boot_caps.type == "hvm":
            return True
        return False

    def get_arch(self):
        return self._arch
    def set_arch(self, arch):
        self._arch = arch
    arch = property(get_arch, set_arch)

    def get_image(self):
        return self._image
    image = property(get_image)

    def get_boot_caps(self):
        return self._boot_caps
    boot_caps = property(get_boot_caps)

    def prepare(self, guest, meter, distro = None):
        self._make_disks(guest)

        # Ugly: for PV xen, there's no guest.features, and nothing to toggle
        if self.type != "xen":
            for f in ['pae', 'acpi', 'apic']:
                if self.boot_caps.features[f] & Cap.FEATURE_ON:
                    guest.features[f] = True
                elif self.boot_caps.features[f] & Cap.FEATURE_OFF:
                    guest.features[f] = False

    def _make_disks(self, guest):
        for m in self.boot_caps.drives:
            p = self._abspath(m.disk.file)
            s = None
            if m.disk.size is not None:
                s = float(m.disk.size)/1024
            # FIXME: This is awkward; the image should be able to express
            # whether the disk is expected to be there or not independently
            # of its classification, especially for user disks
            # FIXME: We ignore the target for the mapping in m.target
            if m.disk.use == ImageParser.Disk.USE_SYSTEM and not os.path.exists(p):
                raise ImageInstallerException(_("System disk %s does not exist")
                                              % p)
            device = Guest.VirtualDisk.DEVICE_DISK
            if m.disk.format == ImageParser.Disk.FORMAT_ISO:
                device = Guest.VirtualDisk.DEVICE_CDROM
            d = Guest.VirtualDisk(p, s,
                                  device = device,
                                  type = Guest.VirtualDisk.TYPE_FILE)
            if self.boot_caps.type == "xen" and util.is_blktap_capable():
                d.driver_name = Guest.VirtualDisk.DRIVER_TAP
            d.target = m.target

            guest._install_disks.append(d)

    def _get_osblob(self, install, hvm, arch = None, loader = None):
        osblob = "<os>\n"

        if hvm:
            os_type = "hvm"
        else:
            # Hack for older libvirt Xen driver
            if self.type == "xen":
                os_type = "linux"
            else:
                os_type = "xen"

        if arch:
            osblob += "    <type arch='%s'>%s</type>\n" % (arch, os_type)
        else:
            osblob += "    <type>%s</type>\n" % os_type

        if loader:
            osblob += "    <loader>%s</loader>\n" % loader
        if self.boot_caps.kernel:
            osblob += "    <kernel>%s</kernel>\n"   % util.xml_escape(self._abspath(self.boot_caps.kernel))
            osblob += "    <initrd>%s</initrd>\n"   % util.xml_escape(self._abspath(self.boot_caps.initrd))
            osblob += "    <cmdline>%s</cmdline>\n" % util.xml_escape(self.boot_caps.cmdline)
            osblob += "  </os>"
        elif hvm:
            if self.boot_caps.bootdev:
                osblob += "    <boot dev='%s'/>\n" % self.boot_caps.bootdev
            osblob += "  </os>"
        elif self.boot_caps.loader == "pygrub" or (self.boot_caps.loader is None and self.boot_caps.type == "xen"):
            osblob += "  </os>\n"
            osblob += "  <bootloader>/usr/bin/pygrub</bootloader>"

        return osblob

    def post_install_check(self, guest):
        return True

    def _abspath(self, p):
        return self.image.abspath(p)

class PlatformMatchException(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

def match_boots(capabilities, boots):
    for b in boots:
        for g in capabilities.guests:
            if b.type == g.os_type and b.arch == g.arch:
                found = True
                for bf in b.features.names():
                    if not b.features[bf] & g.features[bf]:
                        found = False
                        break
                if found:
                    return b
    return None

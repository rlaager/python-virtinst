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

import os

import Installer
import ImageParser
import CapabilitiesParser as Cap
from VirtualDisk import VirtualDisk
from virtinst import _virtinst as _

class ImageInstallerException(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class ImageInstaller(Installer.Installer):
    """Installer for image-based guests"""
    def __init__(self, image, capabilities=None, boot_index=None, conn=None):
        Installer.Installer.__init__(self, conn=conn)

        self._arch = None
        self._image = image

        # Set capabilities
        if self.conn:
            self._capabilities = Cap.parse(self.conn.getCapabilities())
        elif capabilities:
            if not isinstance(capabilities, Cap.Capabilities):
                raise ValueError(_("'capabilities' must be a "
                                   "Capabilities instance."))
            self._capabilities = capabilities
        else:
            raise ValueError(_("'conn' or 'capabilities' must be specified."))

        # Set boot _boot_caps/_boot_parameters
        if boot_index is None:
            self._boot_caps = match_boots(self._capabilities,
                                     self.image.domain.boots)
            if self._boot_caps is None:
                raise ImageInstallerException(_("Could not find suitable boot "
                                                "descriptor for this host"))
        else:
            if (boot_index < 0 or
                (boot_index + 1) > len(image.domain.boots)):
                raise ValueError(_("boot_index out of range."))
            self._boot_caps = image.domain.boots[boot_index]

        # Set up internal caps.guest object
        self._guest = self._capabilities.guestForOSType(self.boot_caps.type,
                                                        self.boot_caps.arch)
        if self._guest is None:
            raise PlatformMatchException(_("Unsupported virtualization type: "
                                           "%s %s" % (self.boot_caps.type,
                                                      self.boot_caps.arch)))

        self.os_type = self.boot_caps.type
        self._domain = self._guest.bestDomainType()
        self.type = self._domain.hypervisor_type
        self.arch = self._guest.arch


    # Custom ImageInstaller methods

    def is_hvm(self):
        if self._boot_caps.type == "hvm":
            return True
        return False

    def get_image(self):
        return self._image
    image = property(get_image)

    def get_boot_caps(self):
        return self._boot_caps
    boot_caps = property(get_boot_caps)


    # General Installer methods

    def prepare(self, guest, meter):
        self.cleanup()

        self._make_disks()

        for f in ['pae', 'acpi', 'apic']:
            if self.boot_caps.features[f] & Cap.FEATURE_ON:
                guest.features[f] = True
            elif self.boot_caps.features[f] & Cap.FEATURE_OFF:
                guest.features[f] = False

    def get_install_xml(self, guest, isinstall):
        if isinstall:
            return None

        kernel = { "kernel" : self.boot_caps.kernel,
                   "initrd" : self.boot_caps.initrd,
                   "extraargs" : self.boot_caps.cmdline }

        return self._get_osblob_helper(guest,
                                       isinstall=bool(self.boot_caps.kernel),
                                       kernel=kernel,
                                       bootdev=self.boot_caps.bootdev)

    def post_install_check(self, guest):
        return True


    # Private methods

    def _make_disks(self):
        for m in self.boot_caps.drives:
            p = self._abspath(m.disk.file)
            s = None
            if m.disk.size is not None:
                s = float(m.disk.size)/1024

            # FIXME: This is awkward; the image should be able to express
            # whether the disk is expected to be there or not independently
            # of its classification, especially for user disks
            # FIXME: We ignore the target for the mapping in m.target
            if (m.disk.use == ImageParser.Disk.USE_SYSTEM and
                not os.path.exists(p)):
                raise ImageInstallerException(_("System disk %s does not exist")
                                              % p)
            device = VirtualDisk.DEVICE_DISK
            if m.disk.format == ImageParser.Disk.FORMAT_ISO:
                device = VirtualDisk.DEVICE_CDROM
            d = VirtualDisk(p, s,
                            device = device,
                            type = VirtualDisk.TYPE_FILE)
            d.target = m.target

            self.install_devices.append(d)

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

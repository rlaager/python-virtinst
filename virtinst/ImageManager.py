# Installer for images
#
# Copyright 2007  Red Hat, Inc.
# David Lutterkort <dlutter@redhat.com>

import Guest
import ImageParser
import CapabilitiesParser as Cap
import os
import util

import pdb

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
            self._boot = None
        else:
            self._boot = image.domain.boots[boot_index]

    def get_image(self):
        return self._image
    image = property(get_image)

    def get_boot(self):
        if self._boot is None:
            self._boot = match_boots(self._capabilities,
                                     self.image.domain.boots)
            if self._boot is None:
                raise ImageInstallerException(_("Could not find suitable boot descriptor for this host"))
        return self._boot
    boot = property(get_boot)

    def get_type(self):
        return domain_type(self._capabilities, self.boot)
    def set_type(self, t):
        pass
    type = property(get_type, set_type)

    def prepare(self, guest, meter, distro = None):
        self._make_disks(guest)

        # Ugly: for PV xen, there's no guest.features, and nothing to toggle
        if self.type != "xen":
            for f in ['pae', 'acpi', 'apic']:
                if self.boot.features[f] & Cap.FEATURE_ON:
                    guest.features[f] = True
                elif self.boot.features[f] & Cap.FEATURE_OFF:
                    guest.features[f] = False

    def _make_disks(self, guest):
        for m in self.boot.disks:
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
            if self.boot.type == "xen" and util.is_blktap_capable():
                d.driver_name = Guest.VirtualDisk.DRIVER_TAP
            d.target = m.target

            guest.disks.append(d)

    def _get_osblob(self, install, hvm, arch = None, loader = None):
        osblob = "<os>\n"

        if hvm:
            type = "hvm"
        else:
            type = "linux"

        if arch:
            osblob += "    <type arch='%s'>%s</type>\n" % (arch, type)
        else:
            osblob += "    <type>%s</type>\n" % type

        if self.boot.kernel:
            osblob += "    <kernel>%s</kernel>\n"   % self._abspath(self.boot.kernel)
            osblob += "    <initrd>%s</initrd>\n"   % self._abspath(self.boot.initrd)
            osblob += "    <cmdline>%s</cmdline>\n" % self.boot.cmdline
            osblob += "  </os>"
        elif hvm:
            if loader:
                osblob += "    <loader>%s</loader>\n" % loader
            if self.boot.bootdev:
                osblob += "    <boot dev='%s'/>\n" % self.boot.bootdev
            osblob += "  </os>"
        elif self.boot.loader == "pygrub" or (self.boot.loader is None and self.boot.type == "xen"):
            osblob += "  </os>\n"
            osblob += "  <bootloader>/usr/bin/pygrub</bootloader>"

        return osblob

    def post_install_check(self, guest):
        return True

    def _abspath(self, p):
        return os.path.abspath(os.path.join(self.image.base, p))

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

def domain_type(capabilities, boot):
    if boot.type == "xen":
        return "xen"
    assert boot.type == "hvm"

    types = [ guest.hypervisor_type for guest in capabilities.guests
                                      if guest.os_type == "hvm" ]
    # FIXME: The order shouldn't be defined here, it should
    # somehow come from libvirt
    order = [ "xen", "kvm", "kqemu", "qemu" ]
    for o in order:
        if types.count(o) > 0:
            return o
    # None of the known types above was found, return the alphabetically
    # smallest one arbitrarily
    types.sort()
    if len(types) > 0:
        return types[0]
    raise PlatformMatchException(_("Insufficient HVM capabilities"))

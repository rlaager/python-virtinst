#!/usr/bin/python -tt
#
# Fullly virtualized guest support
#
# Copyright 2006-2007  Red Hat, Inc.
# Jeremy Katz <katzj@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os
import libvirt
import Guest
import util
import DistroManager
import logging
import time
from virtinst import _virtinst as _


class FullVirtGuest(Guest.XenGuest):
    OS_TYPES = { "linux": { "label": "Linux", \
                            "acpi": True, \
                            "apic": True, \
                            "continue": False, \
                            "variants": { "rhel2.1": { "label": "Red Hat Enterprise Linux 2.1", "distro": "rhel" }, \
                                          "rhel3": { "label": "Red Hat Enterprise Linux 3", "distro": "rhel" }, \
                                          "rhel4": { "label": "Red Hat Enterprise Linux 4", "distro": "rhel" }, \
                                          "rhel5": { "label": "Red Hat Enterprise Linux 5", "distro": "rhel" }, \
                                          "centos5": { "label": "Cent OS 5", "distro": "centos" }, \
                                          "fedora5": { "label": "Fedora Core 5", "distro": "fedora" }, \
                                          "fedora6": { "label": "Fedora Core 6", "distro": "fedora" }, \
                                          "fedora7": { "label": "Fedora 7", "distro": "fedora" }, \
                                          "sles10": { "label": "Suse Linux Enterprise Server", "distro": "suse" }, \
                                          "generic24": { "label": "Generic 2.4.x kernel" }, \
                                          "generic26": { "label": "Generic 2.6.x kernel" }, \
                                          }, \
                            }, \
                 "windows": { "label": "Windows", \
                              "acpi": True, \
                              "apic": True, \
                              "continue": True, \
                              "variants": { "winxp": { "label": "Microsoft Windows XP" }, \
                                            "win2k": { "label": "Microsoft Windows 2000" }, \
                                            "win2k3": { "label": "Microsoft Windows 2003" }, \
                                            "vista": { "label": "Microsoft Windows Vista" }, \
                                            }, \
                              }, \
                 "unix": { "label": "UNIX", \
                           "acpi": True,
                           "apic": True,
                           "continue": False, \
                           "variants": { "solaris9": { "label": "Sun Solaris 9" }, \
                                         "solaris10": { "label": "Sun Solaris 10" }, \
                                         "freebsd6": { "label": "Free BSD 6.x" }, \
                                         "openbsd4": { "label": "Open BSD 4.x" }, \
                                         }, \
                           }, \
                 "other": { "label": "Other", \
                            "acpi": True,
                            "apic": True,
                            "continue": False,
                            "variants": { "msdos": { "label": "MS-DOS" }, \
                                          "netware4": { "label": "Novell Netware 4" }, \
                                          "netware5": { "label": "Novell Netware 5" }, \
                                          "netware6": { "label": "Novell Netware 6" }, \
                                          "generic": { "label": "Generic" }, \
                                          }, \
                            } \
                 }

    def list_os_types():
        return FullVirtGuest.OS_TYPES.keys()
    list_os_types = staticmethod(list_os_types)

    def list_os_variants(type):
        return FullVirtGuest.OS_TYPES[type]["variants"].keys()
    list_os_variants = staticmethod(list_os_variants)

    def get_os_type_label(type):
        return FullVirtGuest.OS_TYPES[type]["label"]
    get_os_type_label = staticmethod(get_os_type_label)

    def get_os_variant_label(type, variant):
        return FullVirtGuest.OS_TYPES[type]["variants"][variant]["label"]
    get_os_variant_label = staticmethod(get_os_variant_label)


    def __init__(self, type=None, arch=None, connection=None, hypervisorURI=None, emulator=None, installer=None):
        if not installer:
            installer = DistroManager.DistroInstaller(type = type)
        Guest.Guest.__init__(self, type, connection, hypervisorURI, installer)
        self.disknode = "hd"
        self.features = { "acpi": None, "pae": util.is_pae_capable(), "apic": None }
        self.arch = arch
        if emulator is None:
            if self.type == "xen":
                if os.uname()[4] in ("x86_64"):
                    emulator = "/usr/lib64/xen/bin/qemu-dm"
                else:
                    emulator = "/usr/lib/xen/bin/qemu-dm"
        self.emulator = emulator
        if self.type == "xen":
            self.loader = "/usr/lib/xen/boot/hvmloader"
        else:
            self.loader = None
        self._os_type = None
        self._os_variant = None


    def get_os_type(self):
        return self._os_type
    def set_os_type(self, val):
        if FullVirtGuest.OS_TYPES.has_key(val):
            self._os_type = val
        else:
            raise ValueError, _("OS type %s does not exist in our dictionary") % val
    os_type = property(get_os_type, set_os_type)

    def get_os_variant(self):
        return self._os_variant
    def set_os_variant(self, val):
        if FullVirtGuest.OS_TYPES[self._os_type]["variants"].has_key(val):
            self._os_variant = val
        else:
            raise ValueError, _("OS variant %(var)s does not exist in our dictionary for OS type %(type)s") % {'var' : val, 'type' : self._os_type}
    os_variant = property(get_os_variant, set_os_variant)

    def set_os_type_parameters(self, os_type, os_variant):
        # explicitly disabling apic and acpi will override OS_TYPES values
        if self.features["acpi"] is None and os_type is not None:
            if os_variant is not None and FullVirtGuest.OS_TYPES[os_type]["variants"][os_variant].has_key("acpi"):
                self.features["acpi"] = FullVirtGuest.OS_TYPES[os_type]["variants"][os_variant]["acpi"]
            else:
                self.features["acpi"] = FullVirtGuest.OS_TYPES[os_type]["acpi"]

        if self.features["apic"] is None and os_type is not None:
            if os_variant is not None and FullVirtGuest.OS_TYPES[os_type]["variants"][os_variant].has_key("apic"):
                self.features["apic"] = FullVirtGuest.OS_TYPES[os_type]["variants"][os_variant]["apic"]
            else:
                self.features["apic"] = FullVirtGuest.OS_TYPES[os_type]["apic"]

    def get_os_distro(self):
        if self.os_type is not None and self.os_variant is not None and "distro" in FullVirtGuest.OS_TYPES[self.os_type]["variants"][self.os_variant]:
            return FullVirtGuest.OS_TYPES[self.os_type]["variants"][self.os_variant]["distro"]
        return None
    os_distro = property(get_os_distro)

    def _get_features_xml(self):
        ret = "<features>\n"
        if self.features:
            ret += "    "
            for (k, v) in self.features.items():
                ret += "<%s/>" %(k,)
            ret += "\n"
        return ret + "  </features>"

    def _get_osblob(self, install):
        osblob = self.installer._get_osblob(install, True, self.arch, self.loader)
        if osblob is None:
            return None

        return "%s\n  %s" % (osblob, self._get_features_xml())

    def _get_device_xml(self, install = True):
        if self.emulator is None:
            return """    <console device='pty'/>
""" + Guest.Guest._get_device_xml(self, install)
        else:
            return ("""    <emulator>%(emulator)s</emulator>
    <console device='pty'/>
""" % { "emulator": self.emulator }) + \
        Guest.Guest._get_device_xml(self, install)

    def validate_parms(self):
        if not self.location:
            raise ValueError, _("A CD must be specified to boot from")
        self.set_os_type_parameters(self.os_type, self.os_variant)
        Guest.Guest.validate_parms(self)

    def _prepare_install(self, meter):
        self._installer.prepare(guest = self,
                                meter = meter,
                                distro = self.os_distro)

    def get_continue_inst(self):
        if self.os_type is not None:
            if self.os_variant is not None and FullVirtGuest.OS_TYPES[self.os_type]["variants"][self.os_variant].has_key("continue"):
                return FullVirtGuest.OS_TYPES[self.os_type]["variants"][self.os_variant]["continue"]
            else:
                return FullVirtGuest.OS_TYPES[self.os_type]["continue"]
        return False

    def continue_install(self, consolecb, meter):
        install_xml = self.get_config_xml(disk_boot = True)
        logging.debug("Starting guest from '%s'" % ( install_xml ))
        meter.start(size=None, text="Starting domain...")
        self.domain = self.conn.createLinux(install_xml, 0)
        if self.domain is None:
            raise RuntimeError, _("Unable to start domain for guest, aborting installation!")
        meter.end(0)

        self.connect_console(consolecb)

        # ensure there's time for the domain to finish destroying if the
        # install has finished or the guest crashed
        if consolecb:
            time.sleep(1)

        # This should always work, because it'll lookup a config file
        # for inactive guest, or get the still running install..
        return self.conn.lookupByName(self.name)

    def _get_disk_xml(self, install = True):
        """Get the disk config in the libvirt XML format"""
        ret = ""
        count = 0
        for d in self.disks:
            backup_path = None
            if d.transient and not install:
                # Libvirt can't handle QEMU having an empty disk path
                if d.device == Guest.VirtualDisk.DEVICE_CDROM and self.type == "xen":
                    backup_path = d.path
                    d.path = None
                else:
                    continue
            if count > 4:
                raise ValueError, _("Can't use more than 4 disks on an HVM guest")
            if d.device == Guest.VirtualDisk.DEVICE_CDROM and count != 2:
                disknode = "%(disknode)s%(dev)c" % { "disknode": self.disknode, "dev": ord('a') + 2 }
            else:
               if count == 2 and d.device != Guest.VirtualDisk.DEVICE_CDROM:
                   # skip "hdc"
                   count += 1
               disknode = "%(disknode)s%(dev)c" % { "disknode": self.disknode, "dev": ord('a') + count }
            ret += d.get_xml_config(disknode)
            if backup_path:
                d.path = backup_path
            count += 1
        return ret

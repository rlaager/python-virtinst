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

class FullVirtGuest(Guest.XenGuest):
    OS_TYPES = { "Linux" : { "Red Hat Enterprise Linux AS 2.1/3" : { "acpi" : True, "apic": True }, \
                             "Red Hat Enterprise Linux 4" : { "acpi" : True, "apic": True }, \
                             "Red Hat Enterprise Linux 5" : { "acpi" : True, "apic": True }, \
                             "Fedora Core 4-6" : { "acpi" : True, "apic": True }, \
                             "Suse Linux Enterprise Server" : { "acpi" : True, "apic": True }, \
                             "Other Linux 2.6 kernel" : { "acpi" : True, "apic": True } }, \
                 "Microsoft Windows" : { "Windows 2000" : { "acpi": False, "apic" : False }, \
                                         "Windows XP" : { "acpi": True, "apic" : True }, \
                                         "Windows Server 2003" : { "acpi": True, "apic" : True }, \
                                         "Windows Vista" : { "acpi": True, "apic" : True } }, \
                 "Novell Netware" : { "Netware 4" : { "acpi": True, "apic": True }, \
                                      "Netware 5" : { "acpi": True, "apic": True }, \
                                      "Netware 6" : { "acpi": True, "apic": True } }, \
                 "Sun Solaris" : { "Solaris 10" : { "acpi": True, "apic": True }, \
                                   "Solaris 9" : { "acpi": True, "apic": True } }, \
                 "Other" : { "MS-DOS" : { "acpi": False, "apic" : False }, \
                             "Free BSD" : { "acpi": True, "apic" : True }, \
                             "Other" : { "acpi": True, "apic" : True } } }

    def __init__(self, type=None, hypervisorURI=None, emulator=None):
        Guest.Guest.__init__(self, type=type, hypervisorURI=hypervisorURI)
        self.disknode = "hd"
        self.features = { "acpi": None, "pae": util.is_pae_capable(), "apic": None }
        if emulator is None:
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
            raise RuntimeError, "OS type %s does not exist in our dictionary" % val
    os_type = property(get_os_type, set_os_type)

    def get_os_variant(self):
        return self._os_variant
    def set_os_variant(self, val):
        if FullVirtGuest.OS_TYPES[self._os_type].has_key(val):
            self._os_variant = val
        else:
            raise RuntimeError, "OS variant %s does not exist in our dictionary for OS type %s" % (val, os_type)
    os_variant = property(get_os_variant, set_os_variant)

    def set_os_type_parameters(self, os_type, os_variant):
        # explicitly disabling apic and acpi will override OS_TYPES values
        acpi = FullVirtGuest.OS_TYPES[os_type][os_variant]["acpi"]
        apic = FullVirtGuest.OS_TYPES[os_type][os_variant]["apic"]
        if self.features["acpi"] == None:
            self.features["acpi"] = acpi
        if self.features["apic"] == None:
            self.features["apic"] = apic

    def _get_features_xml(self):
        ret = ""
        for (k, v) in self.features.items():
            if v:
                ret += "<%s/>" %(k,)
        return ret

    def _get_loader_xml(self):
        if self.loader is None:
            return ""

        return """    <loader>%(loader)s</loader>""" % { "loader": self.loader }

    def _get_os_xml(self, bootdev):
        return """<os>
    <type>hvm</type>
%(loader)s
    <boot dev='%(bootdev)s'/>
  </os>
  <features>
    %(features)s
  </features>""" % \
    { "bootdev": bootdev, \
      "loader": self._get_loader_xml(), \
      "features": self._get_features_xml() }

    def _get_install_xml(self):
        return self._get_os_xml("cdrom")

    def _get_runtime_xml(self):
        return self._get_os_xml("hd")

    def _get_device_xml(self):
        return ("""    <emulator>%(emulator)s</emulator>
    <console device='pty'/>
""" % { "emulator": self.emulator }) + \
               Guest.Guest._get_device_xml(self)

    def validate_parms(self):
        if not self.location:
            raise RuntimeError, "A CD must be specified to boot from"
        self.set_os_type_parameters(self.os_type, self.os_variant)
        Guest.Guest.validate_parms(self)

    def _prepare_install_location(self, meter):
        cdrom = None
        tmpfiles = []
        if self.location.startswith("/"):
            # Huzzah, a local file/device
            cdrom = self.location
        else:
            # If its a http://, ftp://, or nfs:/ we need to fetch boot.iso
            cdrom = DistroManager.acquireBootDisk(self.location, meter, scratchdir=self.scratchdir)
            tmpfiles.append(cdrom)
        self.disks.append(Guest.VirtualDisk(cdrom, device=Guest.VirtualDisk.DEVICE_CDROM, readOnly=True))

        return tmpfiles

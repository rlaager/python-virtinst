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

import os,stat,time,sys
import string

import libvirt

import Guest
import util


class FullVirtGuest(Guest.XenGuest):
    def __init__(self, type=None, hypervisorURI=None, emulator=None):
        Guest.Guest.__init__(self, type=type, hypervisorURI=hypervisorURI)
        self._cdrom = None
        self.disknode = "hd"
        self.features = { "acpi": True, "pae": util.is_pae_capable(), "apic": True }
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

    def get_cdrom(self):
        return self._cdrom
    def set_cdrom(self, val):
        val = os.path.abspath(val)
        if not os.path.exists(val):
            raise ValueError, "CD device must exist!"
        self._cdrom = val
    cdrom = property(get_cdrom, set_cdrom)

    def _get_disk_xml(self):
        # ugh, this is disgusting, but the HVM disk stuff isn't nice :/
        xml = Guest.Guest._get_disk_xml(self)
        if self.cdrom:
            disk = Guest.VirtualDisk(self.cdrom, readOnly = True, device=Guest.VirtualDisk.DEVICE_CDROM)
            # XXX no need to hardcode hdc in newer xen
            xml += disk.get_xml_config("hdc")
        return xml

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
        if not self.cdrom:
            raise RuntimeError, "A CD must be specified to boot from"
        Guest.Guest.validate_parms(self)

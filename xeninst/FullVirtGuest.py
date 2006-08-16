#!/usr/bin/python -tt
#
# Fullly virtualized guest support
#
# Copyright 2006  Red Hat, Inc.
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

import XenGuest

if os.uname()[4] in ("x86_64"):
    qemu = "/usr/lib64/xen/bin/qemu-dm"
else:
    qemu = "/usr/lib/xen/bin/qemu-dm"

class FullVirtGuest(XenGuest.XenGuest):
    def __init__(self):
        XenGuest.XenGuest.__init__(self)
        self._cdrom = None
        self.disknode = "ioemu:hd"

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
        x = XenGuest.XenGuest._get_disk_xml(self)
        lines = x.split("\n")
        if len(lines) > 3:
            lines = lines[:3]
        if stat.S_ISBLK(os.stat(self.cdrom)[stat.ST_MODE]):
            t = "block"
        else:
            t = "file"
        lines.append("<disk type='%(disktype)s' device='cdrom'><source file='%(disk)s'/><target dev='hdc'/><readonly/></disk>\n" %{"disktype": t, "disk": self.cdrom})
        return string.join(lines, "")

    def _get_config_xml(self):
        # FIXME: hard-codes that we're booting from CD as hdd
        return """<domain type='xen'>
  <name>%(name)s</name>
  <os>
    <type>hvm</type>
    <loader>/usr/lib/xen/boot/hvmloader</loader>
    <boot dev='cdrom'/>
  </os>
  <features>
    <acpi/>
  </features>
  <memory>%(ramkb)s</memory>
  <vcpu>%(vcpus)d</vcpu>
  <uuid>%(uuid)s</uuid>
  <on_reboot>destroy</on_reboot>
  <on_poweroff>destroy</on_poweroff>
  <on_crash>destroy</on_crash>
  <devices>
    <emulator>%(qemu)s</emulator>
    %(disks)s
    %(networks)s
    <graphics type='vnc'/>
  </devices>
</domain>
""" % { "qemu": qemu, "name": self.name, "vcpus": self.vcpus, "uuid": self.uuid, "ramkb": self.memory * 1024, "disks": self._get_disk_xml(), "networks": self._get_network_xml() }

    def _get_config_xen(self):
        return """# Automatically generated xen config file
name = "%(name)s"
builder = "hvm"
memory = "%(ram)s"
%(disks)s
%(networks)s
uuid = "%(uuid)s"
device_model = "%(qemu)s"
kernel = "/usr/lib/xen/boot/hvmloader"
vnc = 1
acpi = 1
serial = "pty" # enable serial console
on_reboot   = 'restart'
on_crash    = 'restart'
""" % { "name": self.name, "ram": self.memory, "disks": self._get_disk_xen(), "networks": self._get_network_xen(), "uuid": self.uuid, "qemu": qemu }

    
    def start_install(self, connectConsole = False):
        if not self.cdrom:
            raise RuntimeError, "A CD must be specified to boot from"
        XenGuest.XenGuest.validateParms(self)
        
        conn = libvirt.open(None)
        if conn == None:
            raise RuntimeError, "Unable to connect to hypervisor, aborting installation!"
        try:
            if conn.lookupByName(self.name) is not None:
                raise RuntimeError, "Domain named %s already exists!" %(self.name,)
        except libvirt.libvirtError:
            pass

        self._createDevices()
        cxml = self._get_config_xml()
        print cxml
        self.domain = conn.createLinux(cxml, 0)
        if self.domain is None:
            raise RuntimeError, "Unable to create domain for guest, aborting installation!"

        time.sleep(5)
        # FIXME: if the domain doesn't exist now, it almost certainly crashed.
        # it'd be nice to know that for certain...
        try:
            d = conn.lookupByID(self.domain.ID())
        except libvirt.libvirtError:
            raise RuntimeError, "It appears that your installation has crashed.  You should be able to find more information in the xen logs"


        cf = "/etc/xen/%s" %(self.name,)
        f = open(cf, "w+")
        f.write(self._get_config_xen())
        f.close()
        return 

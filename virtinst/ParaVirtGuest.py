#
# Paravirtualized guest support
#
# Copyright 2006-2007  Red Hat, Inc.
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

import os
import libvirt
import Guest
import DistroManager
from virtinst import _virtinst as _

class ParaVirtGuest(Guest.XenGuest):
    def __init__(self, type=None, connection=None, hypervisorURI=None, installer=None):
        if not installer:
            installer = DistroManager.DistroInstaller(type = type, os_type = "linux")
        Guest.Guest.__init__(self, type, connection, hypervisorURI, installer)
        self.disknode = "xvd"

    def _get_osblob(self, install):
        return self.installer._get_osblob(install, hvm = False)

    def _connectSerialConsole(self):
        cmd = ["/usr/bin/virsh", "console", "%s" %(self.domain.ID(),)]
        child = os.fork()
        if (not child):
            os.execvp(cmd[0], cmd)
            os._exit(1)
        return child

    def get_input_device(self):
        return ("mouse", "xen")

    def validate_parms(self):
        if not self.location and not self.boot:
            raise ValueError, _("A location must be specified to install from")
        Guest.Guest.validate_parms(self)

    def _prepare_install(self, meter):
        Guest.Guest._prepare_install(self, meter)
        self._installer.prepare(guest = self, meter = meter)
        if self._installer.install_disk is not None:
            self._install_disks.append(self._installer.install_disk)


    def _get_disk_xml(self, install = True):
        """Get the disk config in the libvirt XML format"""
        ret = ""
        nodes = {}
        for i in range(16):
            n = "%s%c" % (self.disknode, ord('a') + i)
            nodes[n] = None
        for d in self._install_disks:
            if d.transient and not install:
                continue
            target = d.target
            if target is None:
                for t in sorted(nodes.keys()):
                    if nodes[t] is None:
                        target = t
                        break
            if target is None or nodes[target] is not None:
                raise ValueError, _("Can't use more than 16 disks on a PV guest")
            nodes[target] = True
            ret += d.get_xml_config(target)
        return ret

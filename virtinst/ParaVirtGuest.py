#!/usr/bin/python -tt
#
# Paravirtualized guest support
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
import DistroManager

class ParaVirtGuest(Guest.XenGuest):
    def __init__(self, type=None, connection=None, hypervisorURI=None, installer=None):
        if not installer:
            installer = DistroManager.DistroInstaller(type = type)
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

    def validate_parms(self):
        if not self.location and not self.boot:
            raise RuntimeError, "A location must be specified to install from"
        Guest.Guest.validate_parms(self)

    def _prepare_install(self, meter):
        self._installer.prepare(guest = self, need_bootdev = False, meter = meter)

    def _get_disk_xml(self, install = True):
        """Get the disk config in the libvirt XML format"""
        ret = ""
        count = 0
        for d in self.disks:
            if d.transient and not install:
                continue
            if count > 15:
                raise ValueError, "Can't use more than 16 disks on a PV guest"
            ret += d.get_xml_config("%(disknode)s%(dev)c" % { "disknode": self.disknode, "dev": ord('a') + count })
            count += 1
        return ret

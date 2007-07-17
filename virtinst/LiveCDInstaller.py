#!/usr/bin/python -tt
#
# An installer class for LiveCD images
#
# Copyright 2007  Red Hat, Inc.
# Mark McLoughlin <markmc@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os
import Guest
import CapabilitiesParser
from virtinst import _virtinst as _

class LiveCDInstallerException(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class LiveCDInstaller(Guest.Installer):
    def __init__(self, type = "xen", location = None):
        Guest.Installer.__init__(self, type, location)

    def prepare(self, guest, meter, distro = None):
        self.cleanup()

        if not os.path.exists(self.location):
            raise LiveCDInstallerException(_("LiveCD image '%s' does not exist") % self.location)

        capabilities = CapabilitiesParser.parse(guest.conn.getCapabilities())

        found = False
        for guest_caps in capabilities.guests:
            if guest_caps.os_type == "hvm":
                found = True
                break

        if not found:
            raise LiveCDInstallerException(_("HVM virtualisation not supported; cannot boot LiveCD"))

        disk = Guest.VirtualDisk(self.location,
                                 device = Guest.VirtualDisk.DEVICE_CDROM,
                                 readOnly = True)
        guest.disks.insert(0, disk)

    def _get_osblob(self, install, hvm, arch = None, loader = None):
        if install:
            return None

        osblob  = "<os>\n"
        osblob += "      <type>hvm</type>\n"
        if loader:
            osblob += "      <loader>%s</loader>\n" % loader
        osblob += "      <boot dev='cdrom'/>\n"
        osblob += "    </os>"

        return osblob

    def post_install_check(self, guest):
        return True

